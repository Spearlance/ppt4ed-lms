# Copyright (c) 2025, Frappe and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document

from lms.lms.signup_webhook import queue_signup_webhook
from lms.lms.traffic_source import get_request_traffic_source, traffic_fields


def _moderator_roles():
	"""Lazy import — lms.lms.utils imports from sibling doctype modules
	at top level, so importing LMS_MODERATOR_ROLES at module level here
	creates a circular import that breaks `bench migrate`'s scheduler
	validation pass."""
	from lms.lms.utils import LMS_MODERATOR_ROLES

	return LMS_MODERATOR_ROLES


class LMSEventRegistration(Document):
	def before_insert(self):
		self.set_traffic_source()

	def set_traffic_source(self):
		"""Record which channel brought the member here, for Admin Reports > Sources.

		Mirrors LMSEnrollment.set_traffic_source: only when the member is
		registering themselves from their own browser. The Stripe webhook passes
		the source captured at checkout in explicitly (it has no browser).
		"""
		if self.get("traffic_source") or frappe.session.user != self.member:
			return

		traffic = get_request_traffic_source()
		if traffic:
			self.update(traffic_fields(traffic))

	def after_insert(self):
		# Best-effort, like the course confirmation: a mail problem must never
		# roll back a paid registration or 500 the Stripe webhook into a retry
		# loop. The registration row keeps confirmation_email_sent = 0 so an
		# admin can resend from the event dashboard / Desk.
		try:
			send_confirmation_email(self)
		except Exception:
			frappe.log_error(
				title="Event registration confirmation email failed",
				message=f"member: {self.member}\nevent: {self.event}\n\n{frappe.get_traceback()}",
			)
		self.add_member_to_live_class()
		queue_signup_webhook(self.doctype, self.name)

	def validate(self):
		self.validate_owner()
		self.validate_duplicate_members()
		self.validate_payment()
		self.validate_self_enrollment()
		self.validate_seat_availability()
		self.validate_course_enrollment()

	def validate_owner(self):
		if self.owner == self.member:
			return

		roles = frappe.get_roles()
		if not any(role in roles for role in _moderator_roles()):
			frappe.throw(_("You must be a Moderator to register users for an event."))

	def validate_payment(self):
		paid_event = frappe.db.get_value("LMS Event", self.event, "paid_event")
		if not paid_event:
			return

		# Credit-based registrations (PPT Employee today; future Professional /
		# Company memberships) are validated by their own whitelist functions
		# before reaching here. Mirrors LMSEnrollment.validate_course_enrollment_eligibility.
		if self.credit_source:
			return

		payment = frappe.db.exists(
			"LMS Payment",
			{
				"payment_for_document_type": "LMS Event",
				"payment_for_document": self.event,
				"member": self.member,
				"payment_received": True,
			},
		)
		if not payment:
			frappe.throw(_("Payment is required to register for this event."))
		else:
			self.payment = payment

	def validate_self_enrollment(self):
		event_details = frappe.db.get_value(
			"LMS Event", self.event, ["allow_self_enrollment", "paid_event"], as_dict=True
		)
		if event_details.paid_event:
			return
		if not event_details.allow_self_enrollment and not self.is_admin():
			frappe.throw(_("Enrollment for this event is restricted. Please contact the Administrator."))

	def is_admin(self):
		roles = frappe.get_roles(frappe.session.user)
		return any(role in roles for role in _moderator_roles())

	def validate_duplicate_members(self):
		if frappe.db.exists(
			"LMS Event Registration",
			{"event": self.event, "member": self.member, "name": ["!=", self.name]},
		):
			frappe.throw(_("Member already registered for this event"))

	def validate_seat_availability(self):
		seat_count = frappe.db.get_value("LMS Event", self.event, "seat_count")
		enrolled_count = frappe.db.count("LMS Event Registration", {"event": self.event})
		if seat_count and enrolled_count >= seat_count:
			frappe.throw(_("There are no seats available for this event."))

	def validate_course_enrollment(self):
		courses = frappe.get_all("Batch Course", filters={"parent": self.event}, fields=["course"])

		for course in courses:
			if not frappe.db.exists(
				"LMS Enrollment",
				{"course": course.course, "member": self.member},
			):
				enrollment = frappe.new_doc("LMS Enrollment")
				enrollment.course = course.course
				enrollment.member = self.member
				enrollment.enrollment_from_event = self.event
				enrollment.save()

	def add_member_to_live_class(self):
		live_classes = frappe.get_all("LMS Live Class", {"event_name": self.event}, ["name", "event"])

		for live_class in live_classes:
			if live_class.event:
				frappe.get_doc(
					{
						"doctype": "Event Participants",
						"reference_doctype": "User",
						"reference_docname": self.member,
						"email": self.member,
						"parent": live_class.event,
						"parenttype": "Event",
						"parentfield": "event_participants",
					}
				).save()


@frappe.whitelist()
def send_confirmation_email(doc: Document):
	if isinstance(doc, str):
		doc = frappe._dict(json.loads(doc))

	roles = frappe.get_roles()
	is_admin = any(role in roles for role in _moderator_roles())
	is_member = doc.member == frappe.session.user

	if not is_member and not is_admin:
		frappe.throw(
			_("You do not have permission to send confirmation emails for this enrollment."),
			frappe.PermissionError,
		)

	if not doc.confirmation_email_sent:
		outgoing_email_account = frappe.get_cached_value(
			"Email Account", {"default_outgoing": 1, "enable_outgoing": 1}, "name"
		)
		if not doc.confirmation_email_sent and (outgoing_email_account or frappe.conf.get("mail_login")):
			send_mail(doc)
			frappe.db.set_value(doc.doctype, doc.name, "confirmation_email_sent", 1)


def receipt_args(payment_name):
	"""Receipt lines for a paid registration, from its LMS Payment row.

	Same shape the course confirmation uses (amount_display, payment_reference,
	purchase_date) so the two templates read alike. Empty when there is no
	payment (free event) or the payment was $0 (100% coupon).
	"""
	from frappe.utils import fmt_money, format_date

	empty = {"amount_display": None, "payment_reference": None, "purchase_date": None}
	if not payment_name:
		return empty
	payment = frappe.db.get_value(
		"LMS Payment", payment_name, ["name", "amount", "currency", "creation"], as_dict=True
	)
	if not payment or not payment.amount:
		return empty
	return {
		"amount_display": fmt_money(payment.amount, currency=(payment.currency or "USD").upper()),
		"payment_reference": payment.name,
		"purchase_date": format_date(payment.creation, "long"),
	}


def send_mail(doc):
	from frappe.utils import format_date, format_time, get_url

	from lms.lms.utils import get_lms_route, lms_send_template_mail

	batch = frappe.db.get_value(
		"LMS Event",
		doc.event,
		[
			"name",
			"title",
			"start_date",
			"start_time",
			"medium",
			"zoom_link",
			"confirmation_email_template",
		],
		as_dict=1,
	)

	subject = _("Enrollment Confirmation for {0}").format(batch.title)
	# event_enrollment_confirmation = on-enrollment "you're confirmed" copy.
	# live_class_reminder still exists and is used by the daily reminder cron
	# (lms_live_class.send_live_class_reminder) where "tomorrow" is correct.
	template = "event_enrollment_confirmation"
	# An event-specific or site-wide custom template wins; otherwise the seeded
	# "Event Registration Confirmation" Email Template (editable in /lms
	# Settings -> Email Templates), and the Jinja file as the last fallback.
	template_name = (
		batch.confirmation_email_template
		or frappe.db.get_single_value("LMS Settings", "batch_confirmation_template")
		or "Event Registration Confirmation"
	)

	first_name = frappe.db.get_value("User", doc.member, "first_name") or doc.member_name

	args = {
		"title": batch.title,
		"student_name": doc.member_name,
		"first_name": first_name,
		"start_time": batch.start_time,
		"start_date": batch.start_date,
		"date": batch.start_date,
		"time": batch.start_time,
		"event_date_display": format_date(batch.start_date, "long") if batch.start_date else "",
		"event_time_display": format_time(batch.start_time, "hh:mm a") if batch.start_time else "",
		"medium": batch.medium,
		"name": batch.name,
		"zoom_link": batch.zoom_link,
		"event_url": get_url(get_lms_route(f"events/{batch.name}")),
		"credit_source": doc.get("credit_source"),
		**receipt_args(doc.get("payment")),
	}

	lms_send_template_mail(
		recipients=doc.member,
		default_subject=subject,
		jinja_template=template,
		args=args,
		template_name=template_name,
		header=[_(batch.title), "green"],
		retry=3,
	)

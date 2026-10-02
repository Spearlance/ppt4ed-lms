import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, now_datetime

from lms.lms.signup_webhook import queue_signup_webhook


class CommunityEventRegistration(Document):
	def before_insert(self):
		if not self.registered_on:
			self.registered_on = now_datetime()

	def after_insert(self):
		# A registration that owes a donation is only real once Stripe confirms
		# it, so the webhook for those is queued from the Stripe handler instead.
		if self.payment_status == "Free":
			queue_signup_webhook(self.doctype, self.name)

	def validate(self):
		self.attendee_count = len(self.attendees or [])
		if self.attendee_count < 1:
			frappe.throw(_("At least one attendee is required."))

		# Donation total is recomputed server-side. Trusting any client-supplied
		# value would let someone register 10 kids for $0.
		event = frappe.get_doc("Community Event", self.parent_event)
		extras = max(self.attendee_count - 1, 0)
		per_extra = float(event.additional_attendee_amount or 0)
		self.donation_total = round(extras * per_extra, 2)

		if self.payment_status == "Pending" and self.donation_total <= 0:
			# A signup that owes nothing should never be Pending.
			self.payment_status = "Free"

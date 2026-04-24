# Copyright (c) 2021, FOSS United and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.email.doctype.email_template.email_template import get_email_template
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import nowdate
from frappe.utils.telemetry import capture


class LMSCertificate(Document):
	def validate(self):
		self.validate_criteria()
		self.validate_duplicate_certificate()

	def autoname(self):
		self.name = make_autoname("hash", self.doctype)

	def after_insert(self):
		capture("certificate_issued", "lms")
		self.populate_ceu_fields()
		self.populate_license_info()
		self.send_certification_email()

	def populate_ceu_fields(self):
		"""Copy CEU hours and disciplines from the course to the certificate."""
		if not self.course:
			return
		ceu_hours = frappe.db.get_value("LMS Course", self.course, "ceu_hours")
		if not ceu_hours:
			return
		disciplines = frappe.get_all(
			"CEU Discipline Link",
			filters={"parent": self.course, "parenttype": "LMS Course"},
			fields=["discipline"],
		)
		discipline_names = ", ".join(d.discipline for d in disciplines) if disciplines else ""
		self.db_set("ceu_hours", ceu_hours, update_modified=False)
		self.db_set("ceu_disciplines", discipline_names, update_modified=False)

	def populate_license_info(self):
		"""Freeze the student's State + License # response from the course feedback survey.

		The Course Survey (LMS Quiz with is_survey=1) is attached to every certified
		course per patch v2_0.attach_feedback_survey_to_certified_courses. The second
		question captures license info as free-form text ("FL PT 00000"). We copy the
		answer onto the certificate at mint time so it survives any later edits the
		student makes to their submissions.
		"""
		if not self.course or not self.member:
			return
		submissions = frappe.get_all(
			"LMS Quiz Submission",
			filters={"member": self.member, "course": self.course},
			fields=["name", "quiz"],
			order_by="creation desc",
		)
		for sub in submissions:
			if not frappe.db.get_value("LMS Quiz", sub.quiz, "is_survey"):
				continue
			answer = frappe.db.get_value(
				"LMS Quiz Result",
				{"parent": sub.name, "question": ["like", "%icense%"]},
				"answer",
			)
			if answer:
				self.db_set("license_info", answer.strip(), update_modified=False)
				return

	def send_certification_email(self):
		outgoing_email_account = frappe.get_cached_value(
			"Email Account", {"default_outgoing": 1, "enable_outgoing": 1}, "name"
		)
		if outgoing_email_account or frappe.conf.get("mail_login"):
			self.send_mail()

	def send_mail(self):
		subject = _("Congratulations on getting certified!")
		template = "certification"
		custom_template = frappe.db.get_single_value("LMS Settings", "certification_template")

		course_title = frappe.db.get_value("LMS Course", self.course, "title") if self.course else None
		args = {
			"student_name": self.member_name,
			"course_name": self.course,
			"course_title": course_title,
			"certificate_name": self.name,
			"template": self.template,
		}

		if custom_template:
			email_template = get_email_template(custom_template, args)
			subject = email_template.get("subject")
			content = email_template.get("message")

		attachments = []
		if self.template:
			safe_title = (course_title or self.course or "Certificate").replace("/", "-")
			try:
				attachments.append(
					frappe.attach_print(
						self.doctype,
						self.name,
						print_format=self.template,
						file_name=f"Certificate — {safe_title}",
					)
				)
			except Exception:
				frappe.log_error(
					frappe.get_traceback(),
					f"Certificate PDF attach failed for {self.name}",
				)

		frappe.sendmail(
			recipients=self.member,
			subject=subject,
			template=template if not custom_template else None,
			content=content if custom_template else None,
			args=args,
			header=[subject, "green"],
			attachments=attachments or None,
		)

	def validate_criteria(self):
		self.validate_role_of_owner()
		if self.event_name:
			self.validate_batch_enrollment()
		elif self.course:
			self.validate_course_enrollment()

	def validate_role_of_owner(self):
		roles = frappe.get_roles()
		is_admin = any(role in roles for role in ["Moderator"])
		if not self.course and not self.event_name and not is_admin:
			frappe.throw(_("Course or Event is required to issue a certificate."))

	def validate_batch_enrollment(self):
		if self.event_name:
			is_enrolled = frappe.db.exists(
				"LMS Event Registration", {"event": self.event_name, "member": self.member}
			)
			if not is_enrolled:
				frappe.throw(_("Certification cannot be issued as the member is not enrolled in this event."))

	def validate_course_enrollment(self):
		if self.course:
			is_enrolled = frappe.db.exists("LMS Enrollment", {"course": self.course, "member": self.member})
			if not is_enrolled:
				frappe.throw(
					_("Certification cannot be issued as the member is not enrolled in this course.")
				)

			completion_certificate = frappe.db.get_value("LMS Course", self.course, "enable_certification")
			if completion_certificate:
				progress = frappe.db.get_value(
					"LMS Enrollment", {"course": self.course, "member": self.member}, "progress"
				)
				if progress < 100:
					frappe.throw(
						_("Certification cannot be issued as the member has not completed the course.")
					)

	def validate_duplicate_certificate(self):
		self.validate_course_duplicates()
		self.validate_batch_duplicates()

	def validate_course_duplicates(self):
		if self.course:
			course_duplicates = frappe.get_all(
				"LMS Certificate",
				filters={
					"member": self.member,
					"name": ["!=", self.name],
					"course": self.course,
				},
				fields=["name", "course", "course_title"],
			)
			if len(course_duplicates):
				full_name = frappe.db.get_value("User", self.member, "full_name")
				frappe.throw(
					_("{0} is already certified for the course {1}").format(
						full_name, course_duplicates[0].course_title
					)
				)

	def validate_batch_duplicates(self):
		if self.event_name:
			batch_duplicates = frappe.get_all(
				"LMS Certificate",
				filters={
					"member": self.member,
					"name": ["!=", self.name],
					"event_name": self.event_name,
				},
				fields=["name", "event_name", "event_title"],
			)
			if len(batch_duplicates):
				full_name = frappe.db.get_value("User", self.member, "full_name")
				frappe.throw(
					_("{0} is already certified for the event {1}").format(
						full_name, batch_duplicates[0].event_title
					)
				)

	def on_update(self):
		frappe.share.add_docshare(
			self.doctype,
			self.name,
			self.member,
			write=1,
			share=1,
			flags={"ignore_share_permission": True},
		)


def has_website_permission(doc, ptype, user, verbose=False):
	if ptype in ["read", "print"]:
		return True
	if doc.member == user and ptype == "create":
		return True
	return False


def is_certified(course):
	certificate = frappe.get_all("LMS Certificate", {"member": frappe.session.user, "course": course})
	if len(certificate):
		return certificate[0].name
	return


@frappe.whitelist()
def create_certificate(course: str):
	certificate = is_certified(course)
	if certificate:
		return frappe.db.get_value(
			"LMS Certificate", certificate, ["name", "course", "template"], as_dict=True
		)

	else:
		validate_certification_eligibility(course)
		default_certificate_template = get_default_certificate_template()
		certificate = frappe.get_doc(
			{
				"doctype": "LMS Certificate",
				"member": frappe.session.user,
				"course": course,
				"issue_date": nowdate(),
				"template": default_certificate_template,
			}
		)
		certificate.save(ignore_permissions=True)
		return certificate


def get_default_certificate_template():
	default_certificate_template = frappe.db.get_value(
		"Property Setter",
		{
			"doc_type": "LMS Certificate",
			"property": "default_print_format",
		},
		"value",
	)
	if not default_certificate_template:
		default_certificate_template = frappe.db.get_value(
			"Print Format",
			{
				"doc_type": "LMS Certificate",
			},
		)

	return default_certificate_template


def validate_certification_eligibility(course):
	if not frappe.db.exists("LMS Enrollment", {"course": course, "member": frappe.session.user}):
		frappe.throw(_("You are not enrolled in this course."))

	if not frappe.db.get_value("LMS Course", course, "enable_certification"):
		frappe.throw(_("Certification is not enabled for this course."))

	progress = frappe.db.get_value(
		"LMS Enrollment", {"course": course, "member": frappe.session.user}, "progress"
	)
	if progress < 100:
		frappe.throw(_("You have not completed the course yet."))


def has_permission(doc, ptype="read", user=None):
	user = user or frappe.session.user
	roles = frappe.get_roles(user)
	if "Moderator" in roles:
		return True
	if doc.owner == user:
		return True
	if ptype not in ("read", "select", "print"):
		return False
	return doc.published


def get_permission_query_conditions(user):
	user = user or frappe.session.user
	roles = frappe.get_roles(user)
	if "Moderator" in roles:
		return None
	return """(`tabLMS Certificate`.published = 1)"""

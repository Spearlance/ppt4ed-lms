# Copyright (c) 2021, FOSS United and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import ceil, flt, nowdate


class LMSEnrollment(Document):
	def before_insert(self):
		self.validate_duplicate_enrollment()
		self.validate_course_enrollment_eligibility()
		self.validate_owner()

	def validate_owner(self):
		"""Makes the member as the owner of the document so that users can update their progress"""
		if self.owner != self.member:
			self.owner = self.member

	def on_update(self):
		update_program_progress(self.member)
		self.maybe_auto_mint_certificate()

	def maybe_auto_mint_certificate(self):
		"""Issue a certificate the moment progress crosses 100 on a certified course.

		Only fires on the 0→100 transition. Guarded by the duplicate-check in
		LMSCertificate.validate_duplicate_certificate, but we check here too so
		we never even queue a mint that would throw.
		"""
		if flt(self.progress) < 100:
			return

		before = self.get_doc_before_save()
		previous_progress = flt(before.progress) if before else 0
		if previous_progress >= 100:
			return

		if not frappe.db.get_value("LMS Course", self.course, "enable_certification"):
			return

		if frappe.db.exists("LMS Certificate", {"course": self.course, "member": self.member}):
			return

		template = frappe.db.get_value(
			"Property Setter",
			{"doc_type": "LMS Certificate", "property": "default_print_format"},
			"value",
		) or frappe.db.get_value("Print Format", {"doc_type": "LMS Certificate"})

		try:
			frappe.get_doc(
				{
					"doctype": "LMS Certificate",
					"member": self.member,
					"course": self.course,
					"issue_date": nowdate(),
					"template": template,
					# Reaching progress == 100 on a certified course provably requires
					# submitting the final Course Survey (the survey is a quiz-lesson;
					# lesson completion is gated on an LMS Quiz Submission existing).
					# So publishing here means "finished the course + final survey".
					"published": 1,
				}
			).insert(ignore_permissions=True)
		except Exception:
			frappe.log_error(
				frappe.get_traceback(),
				f"Auto-mint certificate failed for {self.member}/{self.course}",
			)

	def validate_duplicate_enrollment(self):
		existing_enrollment = frappe.db.exists(
			"LMS Enrollment",
			{
				"course": self.course,
				"member": self.member,
				"name": ["!=", self.name],
			},
		)

		if existing_enrollment and existing_enrollment != self.name:
			frappe.throw(_("Student is already enrolled in this course."))

	def validate_course_enrollment_eligibility(self):
		course_details = frappe.db.get_value(
			"LMS Course",
			self.course,
			["published", "disable_self_learning", "paid_course", "course_type"],
			as_dict=True,
		)

		# Resources are always free — skip all payment/eligibility checks
		if course_details.course_type == "Resource":
			return

		if course_details.disable_self_learning and not is_admin():
			frappe.throw(
				_(
					"You cannot enroll in this course as self-learning is disabled. Please contact the Administrator."
				)
			)

		if not course_details.published and not is_admin():
			frappe.throw(_("You cannot enroll in an unpublished course."))

		if course_details.paid_course:
			# Credit-based enrollments (Professional, Company, PPT Employee, One-Off)
			# are validated by their own enrollment functions before reaching here
			if self.credit_source:
				return

			payment = frappe.db.exists(
				"LMS Payment",
				{
					"payment_for_document_type": "LMS Course",
					"payment_for_document": self.course,
					"member": self.member,
					"payment_received": True,
				},
			)

			if not payment:
				frappe.throw(_("You need to complete the payment for this course before enrolling."))


def is_admin():
	# Imported lazily to avoid a circular import — lms.lms.utils
	# imports from this module at top level.
	from lms.lms.utils import LMS_MODERATOR_ROLES

	roles = frappe.get_roles(frappe.session.user)
	return any(role in roles for role in LMS_MODERATOR_ROLES)


def update_program_progress(member):
	programs = frappe.get_all("LMS Program Member", {"member": member}, ["parent", "name"])

	for program in programs:
		total_progress = 0
		courses = frappe.get_all("LMS Program Course", {"parent": program.parent}, pluck="course")
		for course in courses:
			progress = frappe.db.get_value("LMS Enrollment", {"course": course, "member": member}, "progress")
			progress = progress or 0
			total_progress += progress

		average_progress = ceil(total_progress / len(courses))
		frappe.db.set_value("LMS Program Member", program.name, "progress", average_progress)

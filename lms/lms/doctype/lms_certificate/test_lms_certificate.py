# Copyright (c) 2021, FOSS United and Contributors
# See license.txt

import frappe

from lms.lms.test_helpers import BaseTestUtils


class TestLMSCertificate(BaseTestUtils):
	"""Covers the auto-mint hook on LMS Enrollment, license-info freeze from
	the Course Survey submission, and the CEU Discipline Link approval_number
	field persistence."""

	def setUp(self):
		super().setUp()
		self.student = self._create_user(
			"certtest_student@example.com", "Cert", "Student", ["LMS Student"]
		)
		self.instructor = self._create_user(
			"certtest_instructor@example.com", "Cert", "Instructor", ["Course Creator"]
		)
		self.course = self._create_course(
			title="Cert Auto-Mint Course", instructor=self.instructor.email
		)
		self.course.enable_certification = 1
		self.course.save()

	def _enroll_and_complete(self, member, course_name):
		enrollment = self._create_enrollment(member, course_name)
		enrollment.reload()
		enrollment.progress = 100
		enrollment.save(ignore_permissions=True)
		return enrollment

	def test_auto_mint_on_progress_100(self):
		self._enroll_and_complete(self.student.email, self.course.name)
		cert = frappe.db.get_value(
			"LMS Certificate",
			{"course": self.course.name, "member": self.student.email},
			["name", "issue_date"],
			as_dict=True,
		)
		self.assertIsNotNone(cert)
		self.cleanup_items.append(("LMS Certificate", cert.name))

	def test_auto_mint_idempotent(self):
		enrollment = self._enroll_and_complete(self.student.email, self.course.name)
		certs_before = frappe.get_all(
			"LMS Certificate",
			filters={"course": self.course.name, "member": self.student.email},
			pluck="name",
		)
		for c in certs_before:
			self.cleanup_items.append(("LMS Certificate", c))
		# Re-save with progress still 100 — should not create a second cert.
		enrollment.reload()
		enrollment.progress = 100
		enrollment.save(ignore_permissions=True)
		certs_after = frappe.get_all(
			"LMS Certificate",
			filters={"course": self.course.name, "member": self.student.email},
			pluck="name",
		)
		self.assertEqual(len(certs_before), 1)
		self.assertEqual(len(certs_after), 1)

	def test_auto_mint_skipped_when_certification_disabled(self):
		uncertified = self._create_course(
			title="Uncertified Course", instructor=self.instructor.email
		)
		uncertified.enable_certification = 0
		uncertified.save()

		self._enroll_and_complete(self.student.email, uncertified.name)

		cert = frappe.db.get_value(
			"LMS Certificate",
			{"course": uncertified.name, "member": self.student.email},
			"name",
		)
		self.assertIsNone(cert)

	def test_license_info_frozen_from_survey_submission(self):
		# Create a survey quiz with the license question, then a submission with an answer.
		license_question = frappe.new_doc("LMS Question")
		license_question.update(
			{
				"question": "State, Discipline and professional license or certification number (e.g., FL PT 00000)",
				"type": "Open Ended",
			}
		)
		license_question.save()
		self.cleanup_items.append(("LMS Question", license_question.name))

		survey_quiz = frappe.new_doc("LMS Quiz")
		survey_quiz.update(
			{
				"title": "Cert License Survey",
				"passing_percentage": 0,
				"is_survey": 1,
				"questions": [{"question": license_question.name, "marks": 1}],
			}
		)
		survey_quiz.save()
		self.cleanup_items.append(("LMS Quiz", survey_quiz.name))

		submission = frappe.new_doc("LMS Quiz Submission")
		submission.update(
			{
				"quiz": survey_quiz.name,
				"course": self.course.name,
				"member": self.student.email,
				"score": 0,
				"score_out_of": 0,
				"percentage": 0,
				"result": [
					{
						"question": license_question.question,
						"question_name": license_question.name,
						"answer": "FL PT 12345",
						"is_correct": 0,
						"marks": 0,
						"marks_out_of": 1,
					}
				],
			}
		)
		submission.insert(ignore_permissions=True)
		self.cleanup_items.append(("LMS Quiz Submission", submission.name))

		self._enroll_and_complete(self.student.email, self.course.name)

		cert_name = frappe.db.get_value(
			"LMS Certificate",
			{"course": self.course.name, "member": self.student.email},
			"name",
		)
		self.assertIsNotNone(cert_name)
		self.cleanup_items.append(("LMS Certificate", cert_name))
		license_info = frappe.db.get_value("LMS Certificate", cert_name, "license_info")
		self.assertEqual(license_info, "FL PT 12345")

	def test_ceu_discipline_link_persists_approval_number(self):
		discipline_name = "PT/PTA TestDiscipline"
		if not frappe.db.exists("CEU Discipline", discipline_name):
			d = frappe.new_doc("CEU Discipline")
			d.discipline_name = discipline_name
			d.save()
			self.cleanup_items.append(("CEU Discipline", d.name))

		course = self.course
		course.append(
			"disciplines",
			{"discipline": discipline_name, "approval_number": "PENDING-001"},
		)
		course.save()

		row = frappe.db.get_value(
			"CEU Discipline Link",
			{
				"parent": course.name,
				"parenttype": "LMS Course",
				"discipline": discipline_name,
			},
			["discipline", "approval_number"],
			as_dict=True,
		)
		self.assertIsNotNone(row)
		self.assertEqual(row.approval_number, "PENDING-001")

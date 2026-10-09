# Copyright (c) 2021, FOSS United and Contributors
# See license.txt

import json
import re

import frappe
from frappe.utils import add_days, nowdate

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


class TestCertificatePrintFormat(BaseTestUtils):
	"""Renders the Certificate print format straight from the JSON on disk
	(bench migrate does not reload print formats, so the DB row can lag the
	repo) and asserts on signer selection, the On-Demand line, the additional
	presenters line and the credentials toggle."""

	def setUp(self):
		super().setUp()
		self.student = self._create_user(
			"certfmt_student@example.com", "Garrett", "Test", ["LMS Student"]
		)
		self.presenters = [
			self._create_user(
				f"certfmt_presenter{i}@example.com", "Presenter", f"Number{i}", ["Course Creator"]
			)
			for i in range(1, 5)
		]
		self.outsider = self._create_user(
			"certfmt_outsider@example.com", "Outside", "Signer", ["Course Creator"]
		)
		self.course = self._make_course("Cert Format Course", self.presenters)
		self.cert_name = self._mint(self.course.name)

	def _make_course(self, title, instructors):
		"""Like BaseTestUtils._create_course but without the legacy
		`category: Business` link, which does not exist on every site, and
		with every instructor row set up front. New certificate fields are
		explicitly blank so each test starts from the pre-change state."""
		existing = frappe.db.exists("LMS Course", {"title": title})
		if existing:
			frappe.delete_doc("LMS Course", existing, force=True)
		course = frappe.new_doc("LMS Course")
		course.update(
			{
				"title": title,
				"short_introduction": "Certificate print format fixture",
				"description": "Certificate print format fixture course.",
				"published": 1,
				"enable_certification": 1,
				"course_format": "",
				"show_signer_credentials": 0,
				"instructors": [{"instructor": u.email} for u in instructors],
				"certificate_signers": [],
			}
		)
		course.save()
		self.cleanup_items.append(("LMS Course", course.name))
		return course

	def _make_event(self, title, instructors):
		"""Minimal LMS Event (no evaluator / course rows, which
		BaseTestUtils._create_batch links to users that may not exist)."""
		existing = frappe.db.exists("LMS Event", {"title": title})
		if existing:
			frappe.delete_doc("LMS Event", existing, force=True)
		event = frappe.new_doc("LMS Event")
		event.update(
			{
				"title": title,
				"start_date": nowdate(),
				"end_date": add_days(nowdate(), 1),
				"start_time": "09:00:00",
				"end_time": "11:00:00",
				"timezone": "America/New_York",
				"published": 1,
				"description": "Certificate print format fixture event.",
				"event_details": "Certificate print format fixture event.",
				"instructors": [{"instructor": u.email} for u in instructors],
			}
		)
		event.save()
		self.cleanup_items.append(("LMS Event", event.name))
		return event

	def _mint(self, course_name):
		enrollment = self._create_enrollment(self.student.email, course_name)
		enrollment.reload()
		enrollment.progress = 100
		enrollment.save(ignore_permissions=True)
		cert_name = frappe.db.get_value(
			"LMS Certificate", {"course": course_name, "member": self.student.email}, "name"
		)
		self.assertIsNotNone(cert_name)
		self.cleanup_items.append(("LMS Certificate", cert_name))
		return cert_name

	def _set_signers(self, *emails):
		self.course.reload()
		self.course.set("certificate_signers", [{"signer": e} for e in emails])
		self.course.save()

	@staticmethod
	def _render(cert_name):
		path = frappe.get_app_path("lms", "lms", "print_format", "certificate", "certificate.json")
		with open(path, encoding="utf-8") as f:
			html = json.load(f)["html"]
		return frappe.render_template(html, {"doc": frappe.get_doc("LMS Certificate", cert_name)})

	@staticmethod
	def _signature_names(html):
		return re.findall(r'class="cert-sig-name">(.*?)</div>', html)

	@staticmethod
	def _additional_line(html):
		match = re.search(r'class="cert-additional">(.*?)</div>', html)
		return match.group(1) if match else None

	def test_no_signers_falls_back_to_first_two_instructors(self):
		html = self._render(self.cert_name)
		self.assertEqual(self._signature_names(html), ["Presenter Number1", "Presenter Number2"])
		self.assertEqual(
			self._additional_line(html),
			"Additional presenters: Presenter Number3, Presenter Number4",
		)

	def test_certificate_signers_override_instructor_order(self):
		self._set_signers(self.presenters[2].email, self.presenters[0].email)
		html = self._render(self.cert_name)
		self.assertEqual(self._signature_names(html), ["Presenter Number3", "Presenter Number1"])
		# Non-signing instructors are listed in instructor-table order.
		self.assertEqual(
			self._additional_line(html),
			"Additional presenters: Presenter Number2, Presenter Number4",
		)

	def test_signer_outside_instructor_table_signs_alone(self):
		self._set_signers(self.outsider.email)
		html = self._render(self.cert_name)
		self.assertEqual(self._signature_names(html), ["Outside Signer"])
		self.assertEqual(
			self._additional_line(html),
			"Additional presenters: Presenter Number1, Presenter Number2, "
			"Presenter Number3, Presenter Number4",
		)

	def test_more_than_two_signers_is_rejected(self):
		self.course.reload()
		self.course.set(
			"certificate_signers", [{"signer": p.email} for p in self.presenters[:3]]
		)
		with self.assertRaises(frappe.ValidationError):
			self.course.save()

	def test_duplicate_signer_is_rejected(self):
		self.course.reload()
		self.course.set(
			"certificate_signers",
			[{"signer": self.presenters[0].email}, {"signer": self.presenters[0].email}],
		)
		with self.assertRaises(frappe.ValidationError):
			self.course.save()

	def test_on_demand_line_shows_only_when_format_is_on_demand(self):
		html = self._render(self.cert_name)
		self.assertNotIn("On-Demand Course", html)

		frappe.db.set_value("LMS Course", self.course.name, "course_format", "Live")
		html = self._render(self.cert_name)
		self.assertNotIn("On-Demand Course", html)

		frappe.db.set_value("LMS Course", self.course.name, "course_format", "On-Demand")
		html = self._render(self.cert_name)
		self.assertIn('<div class="cert-format">On-Demand Course</div>', html)

	def test_additional_presenters_hidden_when_everyone_signs(self):
		# Two instructors, no explicit signers: identical to the pre-change
		# certificate, so no presenters line and no compact-spacing class.
		two_instructor_course = self._make_course(
			"Cert Format Two Instructors", self.presenters[:2]
		)
		cert_name = self._mint(two_instructor_course.name)

		html = self._render(cert_name)
		self.assertEqual(self._signature_names(html), ["Presenter Number1", "Presenter Number2"])
		self.assertIsNone(self._additional_line(html))
		self.assertNotIn("cert-page--compact", html)
		self.assertNotIn("On-Demand Course", html)

	def test_credentials_print_only_when_toggle_is_on(self):
		frappe.db.set_value("User", self.presenters[0].email, "credentials", "PT, DPT")
		frappe.db.set_value("User", self.presenters[1].email, "credentials", "")

		html = self._render(self.cert_name)
		self.assertEqual(self._signature_names(html), ["Presenter Number1", "Presenter Number2"])

		frappe.db.set_value("LMS Course", self.course.name, "show_signer_credentials", 1)
		html = self._render(self.cert_name)
		# Blank credentials never leave a dangling comma.
		self.assertEqual(
			self._signature_names(html), ["Presenter Number1, PT, DPT", "Presenter Number2"]
		)

	def test_event_certificate_ignores_course_level_settings(self):
		self._set_signers(self.outsider.email)
		frappe.db.set_value("LMS Course", self.course.name, "course_format", "On-Demand")

		event = self._make_event("Cert Format Event", self.presenters[:3])
		self._create_batch_enrollment(self.student.email, event.name)

		cert = frappe.new_doc("LMS Certificate")
		cert.update(
			{
				"event_name": event.name,
				"member": self.student.email,
				"issue_date": frappe.utils.nowdate(),
				"published": 1,
			}
		)
		cert.insert()
		self.cleanup_items.append(("LMS Certificate", cert.name))

		html = self._render(cert.name)
		# Events keep the pre-change behaviour: first two instructors sign,
		# nobody else is listed, no format line, no compact spacing.
		self.assertEqual(self._signature_names(html), ["Presenter Number1", "Presenter Number2"])
		self.assertIsNone(self._additional_line(html))
		self.assertNotIn("On-Demand Course", html)
		self.assertNotIn("cert-page--compact", html)

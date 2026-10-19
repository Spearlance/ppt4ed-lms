"""CEU credit verification on events: Survey Only / Online Quiz / In-Person Quiz.

Covers the certificate gate in maybe_auto_mint_event_certificate, the
online quiz endpoint, and the admin score-recording endpoint.
"""

import json
from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase
from frappe.utils import add_days, today

from lms.lms.ceu_event_admin import get_event_credit_status, record_event_quiz_results
from lms.lms.doctype.lms_event.lms_event import (
	get_credit_event_doc,
	get_credit_quiz_status,
	maybe_auto_mint_event_certificate,
)

REG_MODULE = "lms.lms.doctype.lms_event_registration.lms_event_registration"
CERT_MODULE = "lms.lms.doctype.lms_certificate.lms_certificate"
TITLE_PREFIX = "Garrett Test Credit Verification"
EMAILS = (
	"garrett.test.creditverify1@example.com",
	"garrett.test.creditverify2@example.com",
)


class TestEventCreditVerification(UnitTestCase):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		self._patches = [
			patch(f"{REG_MODULE}.send_confirmation_email"),
			patch(f"{REG_MODULE}.queue_signup_webhook"),
			patch("lms.lms.user.queue_signup_webhook"),
			patch(f"{CERT_MODULE}.LMSCertificate.send_certification_email"),
		]
		for p in self._patches:
			p.start()

		self._cleanup()
		self.users = [self._make_user(email, i) for i, email in enumerate(EMAILS, start=1)]
		self.member = self.users[0]
		self.other = self.users[1]
		self.survey_quiz = self._make_quiz("Survey", is_survey=True)
		self.credit_quiz = self._make_quiz("Credit Quiz", passing_percentage=80, max_attempts=2)

	def tearDown(self):
		frappe.set_user("Administrator")
		self._cleanup()
		for p in self._patches:
			p.stop()
		super().tearDown()

	# ------------------------------------------------------------------ fixtures

	def _make_user(self, email, n):
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "Garrett",
				"last_name": f"Credit {n}",
				"send_welcome_email": 0,
			}
		)
		user.flags.no_welcome_mail = True
		user.insert(ignore_permissions=True)
		user.add_roles("LMS Student")
		return user.name

	def _make_question(self, text, correct="Yes", wrong="No"):
		q = frappe.get_doc(
			{
				"doctype": "LMS Question",
				"question": text,
				"type": "Choices",
				"option_1": correct,
				"is_correct_1": 1,
				"option_2": wrong,
				"is_correct_2": 0,
				"multiple": 0,
			}
		)
		q.insert(ignore_permissions=True)
		return q.name

	def _make_quiz(self, suffix, is_survey=False, passing_percentage=80, max_attempts=0):
		question = self._make_question(f"{TITLE_PREFIX} {suffix} Q1")
		quiz = frappe.get_doc(
			{
				"doctype": "LMS Quiz",
				"title": f"{TITLE_PREFIX} {suffix}",
				"is_survey": 1 if is_survey else 0,
				"passing_percentage": passing_percentage,
				"max_attempts": max_attempts,
				"show_answers": 0,
				"questions": [{"question": question, "marks": 1}],
			}
		)
		quiz.insert(ignore_permissions=True)
		return quiz

	def _make_event(self, mode, suffix, credit_quiz=None, passing=None):
		# Ended yesterday so the survey / quiz window is open.
		day = add_days(today(), -1)
		event = frappe.get_doc(
			{
				"doctype": "LMS Event",
				"title": f"{TITLE_PREFIX} {suffix}",
				"start_date": day,
				"end_date": day,
				"start_time": "09:00:00",
				"end_time": "11:00:00",
				"timezone": "America/New_York",
				"description": "Credit verification test event.",
				"event_details": "Credit verification test event.",
				"instructors": [{"instructor": "Administrator"}],
				"certification": 1,
				"survey_quiz": self.survey_quiz.name,
				"credit_verification": mode,
				"credit_quiz": credit_quiz,
				"credit_passing_percentage": passing if passing is not None else 80,
				"credit_hours": 2,
				"published": 0,
			}
		)
		event.insert(ignore_permissions=True)
		return event.name

	def _register(self, event, member):
		frappe.get_doc({"doctype": "LMS Event Registration", "event": event, "member": member}).insert(
			ignore_permissions=True
		)

	def _answers(self, quiz, correct=True):
		rows = []
		for row in quiz.questions:
			q = frappe.get_doc("LMS Question", row.question)
			rows.append(
				{
					"question_name": row.question,
					"answer": [q.option_1 if correct else q.option_2],
					"type": "Choices",
				}
			)
		return json.dumps(rows)

	def _submit_survey(self, event, member):
		from lms.lms.api import submit_event_survey

		frappe.set_user(member)
		try:
			return submit_event_survey(event, self._answers(self.survey_quiz))
		finally:
			frappe.set_user("Administrator")

	def _submit_quiz(self, event, member, correct=True):
		from lms.lms.api import submit_event_quiz

		frappe.set_user(member)
		try:
			return submit_event_quiz(event, self._answers(self.credit_quiz, correct=correct))
		finally:
			frappe.set_user("Administrator")

	def _cert(self, event, member):
		return frappe.db.get_value("LMS Certificate", {"event_name": event, "member": member}, "name")

	def _cleanup(self):
		events = frappe.get_all("LMS Event", filters={"title": ["like", f"{TITLE_PREFIX}%"]}, pluck="name")
		for doctype in ("LMS Certificate", "LMS Quiz Submission"):
			for name in frappe.get_all(doctype, filters={"event_name": ["in", events or [""]]}, pluck="name"):
				frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
			for name in frappe.get_all(doctype, filters={"member": ["in", list(EMAILS)]}, pluck="name"):
				frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
		for name in frappe.get_all(
			"LMS Event Registration", filters={"event": ["in", events or [""]]}, pluck="name"
		):
			frappe.delete_doc("LMS Event Registration", name, force=True, ignore_permissions=True)
		for name in events:
			frappe.delete_doc("LMS Event", name, force=True, ignore_permissions=True)
		for quiz in frappe.get_all("LMS Quiz", filters={"title": ["like", f"{TITLE_PREFIX}%"]}, pluck="name"):
			frappe.delete_doc("LMS Quiz", quiz, force=True, ignore_permissions=True)
		for q in frappe.get_all(
			"LMS Question", filters={"question": ["like", f"{TITLE_PREFIX}%"]}, pluck="name"
		):
			frappe.delete_doc("LMS Question", q, force=True, ignore_permissions=True)
		for email in EMAILS:
			if frappe.db.exists("User", email):
				frappe.delete_doc("User", email, force=True, ignore_permissions=True)

	# ------------------------------------------------------------------ survey only

	def test_survey_only_mints_on_survey(self):
		event = self._make_event("Survey Only", "SO")
		self._register(event, self.member)

		result = self._submit_survey(event, self.member)

		self.assertTrue(result["certificate"])
		self.assertEqual(self._cert(event, self.member), result["certificate"])

	def test_legacy_null_mode_behaves_as_survey_only(self):
		event = self._make_event("Survey Only", "Legacy")
		frappe.db.set_value("LMS Event", event, "credit_verification", None, update_modified=False)
		self._register(event, self.member)

		self._submit_survey(event, self.member)

		self.assertTrue(self._cert(event, self.member))

	# ------------------------------------------------------------------ online quiz

	def test_online_quiz_fail_then_pass(self):
		event = self._make_event("Online Quiz", "OQ", credit_quiz=self.credit_quiz.name)
		self._register(event, self.member)
		self._submit_survey(event, self.member)
		self.assertIsNone(self._cert(event, self.member), "survey alone must not mint")

		failed = self._submit_quiz(event, self.member, correct=False)
		self.assertFalse(failed["pass"])
		self.assertIsNone(failed["certificate"])
		self.assertIsNone(self._cert(event, self.member))

		passed = self._submit_quiz(event, self.member, correct=True)
		self.assertTrue(passed["pass"])
		self.assertTrue(passed["certificate"])
		self.assertEqual(self._cert(event, self.member), passed["certificate"])

		status = get_credit_quiz_status(get_credit_event_doc(event), self.member)
		self.assertEqual(status.attempts, 2)
		self.assertTrue(status.passed)
		self.assertTrue(status.attempts_exhausted)

	def test_online_quiz_pass_then_survey_mints_on_survey(self):
		event = self._make_event("Online Quiz", "OQ2", credit_quiz=self.credit_quiz.name)
		self._register(event, self.member)

		passed = self._submit_quiz(event, self.member, correct=True)
		self.assertTrue(passed["pass"])
		self.assertIsNone(passed["certificate"], "quiz pass without survey must not mint")

		result = self._submit_survey(event, self.member)
		self.assertTrue(result["certificate"])

	def test_online_quiz_rejects_wrong_mode_and_unregistered(self):
		from lms.lms.api import submit_event_quiz

		survey_only = self._make_event("Survey Only", "OQ3")
		self._register(survey_only, self.member)
		frappe.set_user(self.member)
		try:
			with self.assertRaises(frappe.ValidationError):
				submit_event_quiz(survey_only, self._answers(self.credit_quiz))
		finally:
			frappe.set_user("Administrator")

		online = self._make_event("Online Quiz", "OQ4", credit_quiz=self.credit_quiz.name)
		frappe.set_user(self.other)  # not registered
		try:
			with self.assertRaises(frappe.PermissionError):
				submit_event_quiz(online, self._answers(self.credit_quiz))
		finally:
			frappe.set_user("Administrator")

	def test_admin_override_bypasses_attempt_limit(self):
		event = self._make_event("Online Quiz", "OQ5", credit_quiz=self.credit_quiz.name)
		self._register(event, self.member)
		self._submit_survey(event, self.member)
		self._submit_quiz(event, self.member, correct=False)
		self._submit_quiz(event, self.member, correct=False)
		status = get_credit_quiz_status(get_credit_event_doc(event), self.member)
		self.assertTrue(status.attempts_exhausted)
		self.assertIsNone(self._cert(event, self.member))

		res = record_event_quiz_results(
			event, [{"member": self.member, "percentage": 90, "note": "paper retake"}]
		)

		self.assertTrue(res["recorded"][0]["passed"])
		self.assertTrue(res["recorded"][0]["certificate"])
		self.assertTrue(self._cert(event, self.member))
		status = get_credit_quiz_status(get_credit_event_doc(event), self.member)
		self.assertTrue(status.passed)
		self.assertTrue(status.entered_by_admin)
		self.assertEqual(status.admin_note, "paper retake")
		self.assertEqual(status.attempts, 2, "admin entry must not count as an online attempt")

	# ------------------------------------------------------------------ in-person

	def test_in_person_requires_admin_score(self):
		event = self._make_event("In-Person Quiz", "IP", passing=80)
		self._register(event, self.member)
		self._submit_survey(event, self.member)
		self.assertIsNone(self._cert(event, self.member))

		low = record_event_quiz_results(event, json.dumps([{"member": self.member, "percentage": 50}]))
		self.assertFalse(low["recorded"][0]["passed"])
		self.assertIsNone(self._cert(event, self.member))

		high = record_event_quiz_results(event, [{"member": self.member, "percentage": 85}])
		self.assertTrue(high["recorded"][0]["passed"])
		self.assertEqual(self._cert(event, self.member), high["recorded"][0]["certificate"])

		sub = frappe.get_all(
			"LMS Quiz Submission",
			filters={"event_name": event, "member": self.member, "entered_by_admin": 1},
			fields=["score", "score_out_of", "percentage", "passing_percentage", "graded_by"],
			order_by="creation desc",
			limit=1,
		)[0]
		self.assertEqual((sub.score, sub.score_out_of, sub.percentage, sub.passing_percentage), (85, 100, 85, 80))
		self.assertEqual(sub.graded_by, "Administrator")

	def test_in_person_score_before_survey_mints_on_survey(self):
		event = self._make_event("In-Person Quiz", "IP2")
		self._register(event, self.member)

		res = record_event_quiz_results(event, [{"member": self.member}])  # default 100
		self.assertTrue(res["recorded"][0]["passed"])
		self.assertIsNone(res["recorded"][0]["certificate"])
		self.assertFalse(res["recorded"][0]["survey_submitted"])

		result = self._submit_survey(event, self.member)
		self.assertTrue(result["certificate"])

	def test_record_validation_and_permissions(self):
		survey_only = self._make_event("Survey Only", "IP3")
		self._register(survey_only, self.member)
		with self.assertRaises(frappe.ValidationError):
			record_event_quiz_results(survey_only, [{"member": self.member, "percentage": 100}])

		event = self._make_event("In-Person Quiz", "IP4")
		self._register(event, self.member)
		with self.assertRaises(frappe.ValidationError):
			record_event_quiz_results(event, [{"member": self.other, "percentage": 100}])
		with self.assertRaises(frappe.ValidationError):
			record_event_quiz_results(event, [{"member": self.member, "percentage": 140}])
		with self.assertRaises(frappe.ValidationError):
			record_event_quiz_results(event, [])

		frappe.set_user(self.member)
		try:
			with self.assertRaises(frappe.PermissionError):
				record_event_quiz_results(event, [{"member": self.member, "percentage": 100}])
			with self.assertRaises(frappe.PermissionError):
				get_event_credit_status(event)
		finally:
			frappe.set_user("Administrator")

	def test_credit_status_report(self):
		event = self._make_event("In-Person Quiz", "IP5")
		self._register(event, self.member)
		self._register(event, self.other)
		self._submit_survey(event, self.member)
		record_event_quiz_results(event, [{"member": self.member, "percentage": 95}])

		status = get_event_credit_status(event)

		self.assertEqual(status["mode"], "In-Person Quiz")
		self.assertTrue(status["credit_quiz_required"])
		self.assertEqual(status["passing_percentage"], 80)
		me = status["members"][self.member]
		self.assertTrue(me["survey_submitted"])
		self.assertTrue(me["passed"])
		self.assertEqual(me["best_percentage"], 95)
		self.assertTrue(me["entered_by_admin"])
		self.assertTrue(me["certificate"])
		them = status["members"][self.other]
		self.assertFalse(them["survey_submitted"])
		self.assertFalse(them["passed"])
		self.assertIsNone(them["best_percentage"])
		self.assertIsNone(them["certificate"])

	def test_mint_helper_is_idempotent(self):
		event = self._make_event("Survey Only", "Idem")
		self._register(event, self.member)
		first = self._submit_survey(event, self.member)["certificate"]
		self.assertTrue(first)
		self.assertIsNone(maybe_auto_mint_event_certificate(self.member, event))
		self.assertEqual(frappe.db.count("LMS Certificate", {"event_name": event, "member": self.member}), 1)

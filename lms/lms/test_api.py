import frappe

from lms.lms.api import get_certified_participants, get_course_assessment_progress
from lms.lms.test_helpers import BaseTestUtils


class TestLMSAPI(BaseTestUtils):
	def setUp(self):
		super().setUp()
		self._setup_course_flow()

	def test_certified_participants_with_category(self):
		filters = {"category": "Utility Course"}
		certified_participants = get_certified_participants(filters=filters)
		self.assertEqual(len(certified_participants), 1)
		self.assertEqual(certified_participants[0].member, self.student1.email)

		filters = {"category": "Nonexistent Category"}
		certified_participants_no_match = get_certified_participants(filters=filters)
		self.assertEqual(len(certified_participants_no_match), 0)

	def test_certified_participants_with_open_to_work(self):
		filters = {"open_to_work": 1}
		certified_participants_open_to_work = get_certified_participants(filters=filters)
		self.assertEqual(len(certified_participants_open_to_work), 0)

		frappe.db.set_value("User", self.student1.email, "open_to", "Work")
		certified_participants_open_to_work = get_certified_participants(filters=filters)
		self.assertEqual(len(certified_participants_open_to_work), 1)
		frappe.db.set_value("User", self.student1.email, "open_to", "")

	def test_certified_participants_with_open_to_hiring(self):
		filters = {"hiring": 1}
		certified_participants_hiring = get_certified_participants(filters=filters)
		self.assertEqual(len(certified_participants_hiring), 0)

		frappe.db.set_value("User", self.student1.email, "open_to", "Hiring")
		certified_participants_hiring = get_certified_participants(filters=filters)
		self.assertEqual(len(certified_participants_hiring), 1)
		frappe.db.set_value("User", self.student1.email, "open_to", "")

	def test_course_assessment_progress(self):
		progress = get_course_assessment_progress(self.course.name, self.student1.name)
		progress = frappe._dict(progress)

		self.assertEqual(len(progress.quizzes), 1)
		for quiz in progress.quizzes:
			self.assertEqual(quiz.quiz, self.quiz.name)
			self.assertEqual(quiz.quiz_title, self.quiz.title)
			self.assertEqual(quiz.score, 10)
			self.assertEqual(quiz.percentage, 66)

		self.assertEqual(len(progress.assignments), 1)
		for assignment in progress.assignments:
			self.assertEqual(assignment.assignment, self.assignment.name)
			self.assertEqual(assignment.assignment_title, self.assignment.title)
			self.assertEqual(assignment.status, "Pass")

		self.assertEqual(len(progress.exercises), 1)
		for exercise in progress.exercises:
			self.assertEqual(exercise.exercise, self.programming_exercise.name)
			self.assertEqual(exercise.exercise_title, self.programming_exercise.title)
			self.assertEqual(exercise.status, "Passed")

	def test_quiz_submission(self):
		submission = frappe.get_all(
			"LMS Quiz Submission", filters={"quiz": self.quiz.name, "member": self.student1.name}
		)
		self.assertEqual(len(submission), 1)
		submission = submission[0]
		submission = frappe.get_doc("LMS Quiz Submission", submission.name)

		self.assertEqual(submission.score, 10)
		self.assertEqual(submission.score_out_of, 15)
		self.assertEqual(submission.percentage, 66)
		self.assertEqual(submission.passing_percentage, 70)
		self.assertEqual(len(submission.result), 3)
		for index, result in enumerate(submission.result):
			self.assertEqual(result.question_name, self.quiz.questions[index].question)
			self.assertEqual(
				result.answer,
				self.questions[index].option_1 if index % 2 == 0 else self.questions[index].option_2,
			)
			self.assertEqual(result.is_correct, 1 if index % 2 == 0 else 0)
			self.assertEqual(result.marks, 5 if index % 2 == 0 else 0)


class TestPaidSignupLanding(BaseTestUtils):
	"""Paid signups land on the course/event page; checkout starts there."""

	def _finalize(self, target_type, paid):
		from unittest.mock import patch

		from lms.lms.api import _finalize_signup_enrollment

		with patch("lms.lms.api._is_ppt_employee_email", return_value=False), \
			patch("lms.lms.api.frappe.db.get_value", return_value=1 if paid else 0), \
			patch("lms.lms.api.frappe.db.exists", return_value=True), \
			patch("lms.lms.ceu_stripe.create_one_off_checkout") as course_checkout, \
			patch("lms.lms.ceu_stripe.create_event_checkout") as event_checkout:
			result = _finalize_signup_enrollment(
				email="buyer@example.com",
				full_name="Buyer",
				target_type=target_type,
				target_slug="some-item",
				intent="paid",
				plan_name=None,
				plan_price_id=None,
			)
		return result, course_checkout, event_checkout

	def test_paid_course_signup_lands_on_course_page(self):
		result, course_checkout, _ = self._finalize("course", paid=True)
		self.assertEqual(result["status"], "logged_in")
		self.assertEqual(result["redirect_to"], "/lms/courses/some-item?signup=complete")
		course_checkout.assert_not_called()

	def test_paid_event_signup_lands_on_event_page(self):
		result, _, event_checkout = self._finalize("event", paid=True)
		self.assertEqual(result["status"], "logged_in")
		self.assertEqual(result["redirect_to"], "/lms/events/some-item?signup=complete")
		event_checkout.assert_not_called()

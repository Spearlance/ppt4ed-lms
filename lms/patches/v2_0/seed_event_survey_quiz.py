import frappe


SURVEY_QUIZ_TITLE = "Course Survey"


def execute():
	"""Set the shared 'Course Survey' quiz as the default `survey_quiz` on every
	certified LMS Event that doesn't have one configured yet. Mirrors the
	per-course attachment from `attach_feedback_survey_to_certified_courses`,
	but for events. Submissions for event surveys are keyed by `event_name`
	on LMS Quiz Submission, so the quiz can be shared across both surfaces
	without colliding."""
	quiz_name = frappe.db.get_value(
		"LMS Quiz", {"title": SURVEY_QUIZ_TITLE, "is_survey": 1}, "name"
	)
	if not quiz_name:
		# `attach_feedback_survey_to_certified_courses` hasn't run yet (or was
		# rolled back); nothing to backfill. The next migrate cycle will pick
		# this up once the prior patch creates the shared quiz.
		return

	events = frappe.get_all(
		"LMS Event",
		filters={"certification": 1},
		fields=["name", "survey_quiz"],
	)
	for event in events:
		if event.survey_quiz:
			continue
		frappe.db.set_value(
			"LMS Event", event.name, "survey_quiz", quiz_name, update_modified=False
		)

	frappe.db.commit()

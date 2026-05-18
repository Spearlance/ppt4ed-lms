"""
Convert the survey license-number question from "Open Ended" to "Short Text"
so it renders as a single-line input instead of a WYSIWYG editor.

Targets only the license-number question text seeded by oneoff_populate_courses.py;
other Open Ended survey questions (qualitative feedback) keep the rich editor.
"""

import frappe


LICENSE_TEXT_FRAGMENT = "professional license or certification number"


def execute():
	question_names = frappe.get_all(
		"LMS Question",
		filters={
			"type": "Open Ended",
			"question": ["like", f"%{LICENSE_TEXT_FRAGMENT}%"],
		},
		pluck="name",
	)

	for q_name in question_names:
		frappe.db.set_value("LMS Question", q_name, "type", "Short Text")

	# Child LMS Quiz Question rows fetch_from the parent question; mirror the value
	# so the Select renders correctly without waiting for a parent re-save.
	for q_name in question_names:
		frappe.db.sql(
			"""
			UPDATE `tabLMS Quiz Question`
			SET type = 'Short Text'
			WHERE question = %s
			""",
			(q_name,),
		)

	frappe.db.commit()

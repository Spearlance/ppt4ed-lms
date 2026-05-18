"""
Convert post-course survey identity questions ("Full Name", "Confirm Email",
"Therapy Discipline (...)") from "Open Ended" to "Short Text" so they render as
single-line inputs instead of a WYSIWYG editor.

Sibling of convert_license_question_to_short_text -- the earlier patch only
covered the license-number question. Qualitative survey questions
("What did you like most...", "Share 1 takeaway...") keep the rich editor.
"""

import frappe


TARGET_QUESTIONS = [
	"Full Name",
	"Confirm Email",
	"Therapy Discipline (PT/PTA, OT/OTA, SLP/SLPA, Other)",
]


def execute():
	question_names = frappe.get_all(
		"LMS Question",
		filters={
			"type": "Open Ended",
			"question": ["in", TARGET_QUESTIONS],
		},
		pluck="name",
	)

	for q_name in question_names:
		frappe.db.set_value("LMS Question", q_name, "type", "Short Text")

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

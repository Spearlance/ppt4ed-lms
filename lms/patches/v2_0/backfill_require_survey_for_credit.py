"""Backfill LMS Event.require_survey_for_credit so existing events keep
their current behaviour.

Before this field existed, an attached survey_quiz always gated the event
certificate (maybe_auto_mint_event_certificate refused to mint until the
survey was in). The new setting makes that explicit and lets an event carry
an optional survey. Every certified, non-Manual event with a survey attached
therefore gets the flag turned on; nothing else changes. Idempotent.
"""

import frappe


def execute():
	if not frappe.db.has_column("LMS Event", "require_survey_for_credit"):
		frappe.reload_doc("lms", "doctype", "lms_event")

	frappe.db.sql(
		"""
		UPDATE `tabLMS Event`
		SET require_survey_for_credit = 1
		WHERE certification = 1
		  AND IFNULL(survey_quiz, '') != ''
		  AND IFNULL(credit_verification, 'Survey Only') != 'Manual'
		  AND IFNULL(require_survey_for_credit, 0) = 0
		"""
	)

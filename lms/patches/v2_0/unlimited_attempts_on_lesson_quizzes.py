import frappe


def execute():
	"""Backfill max_attempts=0 (unlimited) on all lesson-attached quizzes.

	Lesson-attached quizzes should allow unlimited retakes by default so
	learners can master the material. Standalone quizzes (no lesson link —
	typically certification assessments) keep their configured cap.
	"""
	updated = frappe.db.sql("""
		UPDATE `tabLMS Quiz`
		SET max_attempts = 0
		WHERE lesson IS NOT NULL
		  AND max_attempts > 0
	""")
	frappe.db.commit()

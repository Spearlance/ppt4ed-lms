import frappe


def execute():
	"""Copy the legacy single-select `LMS Course.category` Link into the new
	`categories` Table MultiSelect.

	Mirrors the prior `migrate_event_category_to_multiselect` patch.

	The legacy field is kept on the doctype (hidden, read-only) for one cycle
	so this migration is reversible. A follow-up PR can drop the field after
	verifying no consumers read it.
	"""
	frappe.reload_doc("lms", "doctype", "lms_course_category")
	frappe.reload_doc("lms", "doctype", "lms_course")

	rows = frappe.db.sql(
		"""SELECT name, category FROM `tabLMS Course` WHERE category IS NOT NULL AND category != ''""",
		as_dict=True,
	)

	for row in rows:
		if frappe.db.exists(
			"LMS Course Category",
			{"parent": row.name, "parenttype": "LMS Course", "category": row.category},
		):
			continue

		child = frappe.new_doc("LMS Course Category")
		child.update({
			"parent": row.name,
			"parenttype": "LMS Course",
			"parentfield": "categories",
			"category": row.category,
		})
		child.db_insert()

	frappe.db.commit()

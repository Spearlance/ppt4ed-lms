import frappe


def execute():
	"""Copy the legacy single-select `LMS Event.category` Link into the new
	`categories` Table MultiSelect.

	The legacy field is kept on the doctype (hidden, read-only) for one cycle
	so this migration is reversible. A follow-up PR can drop the field after
	verifying no consumers read it.
	"""
	frappe.reload_doc("lms", "doctype", "lms_event_category")
	frappe.reload_doc("lms", "doctype", "lms_event")

	# Read the legacy column directly so this stays correct even if the
	# field is hidden — `frappe.get_all` honors the JSON definition.
	rows = frappe.db.sql(
		"""SELECT name, category FROM `tabLMS Event` WHERE category IS NOT NULL AND category != ''""",
		as_dict=True,
	)

	for row in rows:
		if frappe.db.exists(
			"LMS Event Category",
			{"parent": row.name, "parenttype": "LMS Event", "category": row.category},
		):
			continue

		child = frappe.new_doc("LMS Event Category")
		child.update({
			"parent": row.name,
			"parenttype": "LMS Event",
			"parentfield": "categories",
			"category": row.category,
		})
		child.db_insert()

	frappe.db.commit()

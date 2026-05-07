import frappe


def execute():
	"""Populate the new `route` field on existing LMS Course / LMS Event rows so
	the public Jinja landing pages at /c/<slug> and /e/<slug> resolve
	immediately after migrate. New saves auto-fill via `set_route()` in
	`validate()`; this patch handles the back-catalog.
	"""
	frappe.reload_doctype("LMS Course")
	frappe.reload_doctype("LMS Event")

	for course in frappe.get_all(
		"LMS Course", filters={"route": ["in", [None, ""]]}, pluck="name"
	):
		frappe.db.set_value("LMS Course", course, "route", f"c/{course}", update_modified=False)

	for event in frappe.get_all(
		"LMS Event", filters={"route": ["in", [None, ""]]}, pluck="name"
	):
		frappe.db.set_value("LMS Event", event, "route", f"e/{event}", update_modified=False)

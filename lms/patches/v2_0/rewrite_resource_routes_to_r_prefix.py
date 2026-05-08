import frappe


def execute():
	"""Flip existing LMS Resource routes from `c/<slug>` to `r/<slug>`.

	The public Jinja landing for resources lives at /r/<slug> alongside the
	course landing at /c/<slug>. Older Resource rows were backfilled to
	`c/<slug>` by `backfill_course_event_routes`; correct them now so each
	doc type owns its own URL prefix. New saves auto-fill via `_sync_route()`
	in `LMSCourse.validate()`.

	Routes that don't match the auto-generated `c/<name>` shape are left
	alone — admin-customized routes stay intact.
	"""
	frappe.reload_doctype("LMS Course")

	resources = frappe.get_all(
		"LMS Course",
		filters={"course_type": "Resource"},
		fields=["name", "route"],
	)
	for resource in resources:
		expected_old = f"c/{resource.name}"
		expected_new = f"r/{resource.name}"
		if resource.route == expected_old:
			frappe.db.set_value(
				"LMS Course", resource.name, "route", expected_new, update_modified=False
			)
		elif not resource.route:
			frappe.db.set_value(
				"LMS Course", resource.name, "route", expected_new, update_modified=False
			)

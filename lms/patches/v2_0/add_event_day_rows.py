import frappe


def execute():
	"""Backfill the new `event_days` child table for every existing LMS Event.

	Per-day start/end times are now stored in `LMS Event Day` rows. Existing
	events have only one start_date/start_time/end_date/end_time pair, so we
	create one child row per event mirroring those values. Multi-day events
	created before this migration end up with a single row and can be edited
	to add per-day variations.
	"""
	frappe.reload_doc("lms", "doctype", "lms_event_day")
	frappe.reload_doc("lms", "doctype", "lms_event")

	events = frappe.get_all(
		"LMS Event",
		fields=["name", "start_date", "start_time", "end_time"],
	)

	for event in events:
		if frappe.db.exists("LMS Event Day", {"parent": event.name, "parenttype": "LMS Event"}):
			continue
		if not (event.start_date and event.start_time and event.end_time):
			continue

		row = frappe.new_doc("LMS Event Day")
		row.update({
			"parent": event.name,
			"parenttype": "LMS Event",
			"parentfield": "event_days",
			"date": event.start_date,
			"start_time": event.start_time,
			"end_time": event.end_time,
		})
		row.db_insert()

	frappe.db.commit()

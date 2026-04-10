import frappe


def get_first_course():
	course = frappe.get_all(
		"LMS Course",
		fields=["name"],
		order_by="creation",
		limit=1,
	)
	return course[0].name if course else None


def get_first_event():
	event = frappe.get_all(
		"LMS Event",
		fields=["name"],
		order_by="creation",
		limit=1,
	)
	return event[0].name if event else None

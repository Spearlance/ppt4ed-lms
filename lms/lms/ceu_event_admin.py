"""Admin tools for managing event registrations from the LMS UI.

Staff (Moderator / System Manager / Global Admin) don't have Desk access on
prod, so anything they need to do to a roster has to live behind a whitelisted
method the Vue admin dashboard can call.
"""

import json

import frappe
from frappe import _
from frappe.utils import cint, flt


def _require_event_admin():
	from lms.lms.utils import LMS_MODERATOR_ROLES

	roles = frappe.get_roles()
	if not any(role in roles for role in LMS_MODERATOR_ROLES):
		frappe.throw(
			_("Only LMS admins can remove event registrations."),
			frappe.PermissionError,
		)


def _parse_names(registrations) -> list[str]:
	if isinstance(registrations, str):
		try:
			registrations = json.loads(registrations)
		except ValueError:
			registrations = [registrations]
	if not isinstance(registrations, (list, tuple)):
		registrations = [registrations]
	return [str(r) for r in registrations if r]


def _remove_event_enrollments(event: str, member: str) -> tuple[list[str], list[str]]:
	"""Delete course enrollments the event created for this member, but only
	while they have no progress. Anything with progress or a certificate is
	kept so we never wipe someone's coursework."""
	removed, kept = [], []
	enrollments = frappe.get_all(
		"LMS Enrollment",
		filters={"member": member, "enrollment_from_event": event},
		fields=["name", "course", "progress", "certificate"],
	)
	for enrollment in enrollments:
		if flt(enrollment.progress) > 0 or enrollment.certificate:
			kept.append(enrollment.course)
			continue
		try:
			frappe.delete_doc("LMS Enrollment", enrollment.name, ignore_permissions=True)
			removed.append(enrollment.course)
		except frappe.LinkExistsError:
			kept.append(enrollment.course)
	return removed, kept


def _remove_live_class_participant(event: str, member: str):
	"""Undo LMSEventRegistration.add_member_to_live_class."""
	calendar_events = frappe.get_all(
		"LMS Live Class",
		filters={"event_name": event, "event": ["is", "set"]},
		pluck="event",
	)
	for calendar_event in calendar_events:
		participants = frappe.get_all(
			"Event Participants",
			filters={
				"parent": calendar_event,
				"parenttype": "Event",
				"reference_doctype": "User",
				"reference_docname": member,
			},
			pluck="name",
		)
		for participant in participants:
			frappe.delete_doc("Event Participants", participant, ignore_permissions=True)


@frappe.whitelist()
def remove_event_registrations(event: str, registrations) -> dict:
	"""Remove one or more people from an event roster.

	Frees their seats (seat availability is a live count of registration rows),
	removes untouched course enrollments the event created, and takes them off
	any live-class calendar invite. Payments are never touched: a paid
	registration is reported back so the admin knows a Stripe refund is a
	separate step. Deleted registrations land in Deleted Documents, so they can
	be restored, and each removal is logged as a comment on the event.
	"""
	_require_event_admin()

	if not frappe.db.exists("LMS Event", event):
		frappe.throw(_("Event {0} not found.").format(event))

	names = _parse_names(registrations)
	if not names:
		frappe.throw(_("Select at least one registration to remove."))

	rows = frappe.get_all(
		"LMS Event Registration",
		filters={"name": ["in", names]},
		fields=["name", "event", "member", "member_name", "payment"],
	)
	found = {r.name for r in rows}
	missing = [n for n in names if n not in found]
	if missing:
		frappe.throw(_("Registration not found: {0}").format(", ".join(missing)))
	wrong_event = [r.name for r in rows if r.event != event]
	if wrong_event:
		frappe.throw(_("These registrations are not for this event: {0}").format(", ".join(wrong_event)))

	removed, paid, kept_courses = [], [], []
	actor = frappe.utils.get_fullname(frappe.session.user)

	for row in rows:
		label = row.member_name or row.member
		_removed_courses, kept = _remove_event_enrollments(event, row.member)
		if kept:
			kept_courses.append({"member": row.member, "member_name": label, "courses": kept})
		_remove_live_class_participant(event, row.member)

		frappe.delete_doc("LMS Event Registration", row.name, ignore_permissions=True)

		if row.payment:
			payment = frappe.db.get_value(
				"LMS Payment", row.payment, ["amount", "currency"], as_dict=True
			) or {}
			if flt(payment.get("amount")) > 0:
				paid.append(
					{
						"member": row.member,
						"member_name": label,
						"payment": row.payment,
						"amount": flt(payment.get("amount")),
						"currency": payment.get("currency") or "USD",
					}
				)

		frappe.get_doc("LMS Event", event).add_comment(
			"Info",
			_("{0} removed {1} ({2}) from this event.").format(actor, label, row.member),
		)
		removed.append({"member": row.member, "member_name": label})

	seat_count = cint(frappe.db.get_value("LMS Event", event, "seat_count"))
	registered = frappe.db.count("LMS Event Registration", {"event": event})

	return {
		"removed": removed,
		"paid": paid,
		"kept_courses": kept_courses,
		"registered": registered,
		"seats_left": max(seat_count - registered, 0) if seat_count else None,
	}

"""Cancelling an event that will not go ahead.

An event with registrations cannot be deleted (see `api.delete_event`), so
this is how PPT calls one off. Cancelling:

- marks the event cancelled and unpublishes it, which takes it off the public
  listings and landing page, closes registration and stops every reminder
  (all of those already key off `published`);
- keeps it visible to the people who registered, with a cancelled notice;
- optionally emails the registered attendees. That is the admin's choice each
  time; nothing is sent unless they tick the box.

Refunds are not handled here. PPT issues them directly in Stripe.
"""

import frappe
from frappe import _
from frappe.utils import cint, format_date, now_datetime

from lms.lms.utils import can_modify_event, lms_send_template_mail

MAX_MESSAGE_LENGTH = 1000


def _require_admin(event: str):
	if frappe.session.user == "Guest" or not can_modify_event(event):
		frappe.throw(_("You do not have permission to cancel this event."), frappe.PermissionError)
	if not frappe.db.exists("LMS Event", event):
		frappe.throw(_("Event {0} not found.").format(event), frappe.DoesNotExistError)


def _registrants(event: str) -> list:
	return frappe.get_all(
		"LMS Event Registration",
		filters={"event": event},
		fields=["member", "member_name"],
		order_by="creation",
	)


@frappe.whitelist()
def get_cancel_info(event: str) -> dict:
	"""What the admin needs to see before cancelling."""
	_require_admin(event)
	row = frappe.db.get_value(
		"LMS Event", event, ["cancelled", "cancelled_on", "cancellation_message", "paid_event"], as_dict=True
	)
	return {
		"registrations": frappe.db.count("LMS Event Registration", {"event": event}),
		"paid_event": cint(row.paid_event),
		"cancelled": cint(row.cancelled),
		"cancelled_on": row.cancelled_on,
		"cancellation_message": row.cancellation_message or "",
	}


@frappe.whitelist(methods=["POST"])
def cancel_event(event: str, notify: int | str = 0, message: str = "") -> dict:
	"""Cancel `event`. With `notify`, email every registered attendee.

	Returns how many emails were queued so the admin sees exactly what went out.
	"""
	_require_admin(event)
	message = (message or "").strip()
	if len(message) > MAX_MESSAGE_LENGTH:
		frappe.throw(_("The message can be at most {0} characters.").format(MAX_MESSAGE_LENGTH))

	doc = frappe.get_doc("LMS Event", event, for_update=True)
	if doc.cancelled:
		frappe.throw(_("This event is already cancelled."))

	doc.flags.cancellation_change = True
	doc.cancelled = 1
	doc.cancelled_on = now_datetime()
	doc.cancellation_message = message
	doc.published = 0
	# The role gate above is the permission check.
	doc.save(ignore_permissions=True)

	notified = 0
	if cint(notify):
		notified = _send_cancellation_emails(doc)

	return {"cancelled": 1, "notified": notified}


@frappe.whitelist(methods=["POST"])
def restore_event(event: str) -> dict:
	"""Undo a cancellation. The event stays unpublished; publishing it again
	is a separate, deliberate step in the event settings. Sends nothing."""
	_require_admin(event)
	doc = frappe.get_doc("LMS Event", event, for_update=True)
	if not doc.cancelled:
		frappe.throw(_("This event is not cancelled."))

	doc.flags.cancellation_change = True
	doc.cancelled = 0
	doc.cancelled_on = None
	doc.cancellation_message = ""
	doc.save(ignore_permissions=True)
	return {"cancelled": 0}


def _send_cancellation_emails(doc) -> int:
	"""Queue one email per registered attendee. A failure for one recipient
	is logged and does not stop the rest or undo the cancellation."""
	sent = 0
	for row in _registrants(doc.name):
		try:
			first_name = frappe.db.get_value("User", row.member, "first_name")
			lms_send_template_mail(
				recipients=row.member,
				default_subject=_("Cancelled: {0}").format(doc.title),
				jinja_template="event_cancelled",
				args={
					"first_name": first_name or row.member_name,
					"title": doc.title,
					"date": format_date(doc.start_date, "long") if doc.start_date else "",
					"message": doc.cancellation_message or "",
					"paid_event": cint(doc.paid_event),
				},
				template_name="Event Cancelled",
				header=[_("Event cancelled"), "red"],
			)
			sent += 1
		except Exception:
			frappe.log_error(
				title="Event cancellation email failed",
				message=f"{doc.name} -> {row.member}\n{frappe.get_traceback()}",
			)
	return sent

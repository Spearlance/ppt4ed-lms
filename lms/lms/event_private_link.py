"""Private registration link for an event.

For groups whose seats are already paid for (a facility that prepaid, a
partner cohort): the event stays unpublished, so it never shows in the
catalog or at /e/<slug>, and the organizer hands the group one unlisted link.
Anyone who opens it can log in or create an account and register for free.

The code in the link is never stored. It is an HMAC of the event name and a
per-event version counter, keyed with the site's encryption key, so nothing
readable through the LMS Event document gives it away. "Reset link" bumps the
counter, which kills every copy of the old link.

Admin endpoints gate on `can_modify_event` and then bypass doctype
permissions, like the other event admin modules.
"""

import hashlib
import hmac

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import cint, get_datetime, get_url, now_datetime
from frappe.utils.password import get_encryption_key

from lms.lms.utils import can_modify_event, get_lms_route

CODE_LENGTH = 24

EVENT_FIELDS = [
	"name",
	"title",
	"description",
	"start_date",
	"end_date",
	"start_time",
	"end_time",
	"timezone",
	"event_type",
	"venue",
	"credit_hours",
	"seat_count",
	"paid_event",
	"cancelled",
	"private_registration_enabled",
	"private_registration_version",
]


def private_link_code(event: str, version: int) -> str:
	message = f"lms-event-private-registration:{event}:{cint(version)}"
	digest = hmac.new(get_encryption_key().encode(), message.encode(), hashlib.sha256)
	return digest.hexdigest()[:CODE_LENGTH]


def private_link_url(event: str, version: int) -> str:
	return get_url(get_lms_route(f"events/{event}/join/{private_link_code(event, version)}"))


def _invalid_link():
	# One message for every failure (unknown event, link turned off, wrong or
	# reset code) so the endpoint cannot be used to probe for private events.
	frappe.throw(
		_("This registration link is not valid. Please ask the organizer for a new one."),
		frappe.PermissionError,
	)


def _get_event_for_code(event: str, code: str):
	row = frappe.db.get_value("LMS Event", event, EVENT_FIELDS, as_dict=True) if event else None
	if not row or not row.private_registration_enabled:
		_invalid_link()
	expected = private_link_code(row.name, row.private_registration_version)
	if not hmac.compare_digest(expected, str(code or "")):
		_invalid_link()
	return row


def _closed_reason(row):
	"""Why nobody can register through the link right now, or None."""
	if row.cancelled:
		return _("This event has been cancelled.")
	if row.paid_event:
		return _("Registration for this event is handled at checkout.")
	if now_datetime() > get_datetime(f"{row.end_date} {row.end_time}"):
		return _("This event has ended.")
	if row.seat_count and frappe.db.count("LMS Event Registration", {"event": row.name}) >= row.seat_count:
		return _("There are no seats available for this event.")
	return None


def _instructor_names(event: str) -> list[str]:
	users = frappe.get_all(
		"Course Instructor",
		filters={"parent": event, "parenttype": "LMS Event"},
		pluck="instructor",
		order_by="idx",
	)
	return [frappe.db.get_value("User", user, "full_name") or user for user in users]


def _is_registered(event: str, user: str) -> bool:
	return bool(frappe.db.exists("LMS Event Registration", {"event": event, "member": user}))


# ------------------------------------------------------------------ attendee


@frappe.whitelist(allow_guest=True)  # nosemgrep: frappe-semgrep-rules.rules.security.guest-whitelisted-method
@rate_limit(limit=120, seconds=60 * 60)
def get_private_registration_info(event: str, code: str) -> dict:
	"""What the join page shows. Guest-callable, but only with a valid code."""
	from lms.lms.license import is_license_complete

	row = _get_event_for_code(event, code)
	user = frappe.session.user
	logged_in = user != "Guest"
	return {
		"name": row.name,
		"title": row.title,
		"description": row.description,
		"start_date": row.start_date,
		"start_time": row.start_time,
		"end_time": row.end_time,
		"timezone": row.timezone,
		"event_type": row.event_type,
		"venue": row.venue,
		"credit_hours": row.credit_hours,
		"instructors": _instructor_names(row.name),
		"logged_in": logged_in,
		"registered": logged_in and _is_registered(row.name, user),
		"license_complete": logged_in and is_license_complete(user),
		"closed_reason": _closed_reason(row),
	}


@frappe.whitelist(methods=["POST"])
def register_with_private_link(event: str, code: str) -> dict:
	"""Register the logged-in user through a private link. Idempotent."""
	from lms.lms.license import require_complete_license

	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Please log in to register."), frappe.AuthenticationError)

	row = _get_event_for_code(event, code)
	if _is_registered(row.name, user):
		return {"status": "registered", "already_registered": True, "event": row.name}

	reason = _closed_reason(row)
	if reason:
		frappe.throw(reason)

	# Same gate as every other event registration: the CEU broker report
	# needs the attendee's license.
	require_complete_license(user)

	registration = frappe.get_doc(
		{
			"doctype": "LMS Event Registration",
			"event": row.name,
			"member": user,
			"member_name": frappe.db.get_value("User", user, "full_name"),
		}
	)
	# The event has self-enrollment off (it is private); the valid code is
	# what authorises this registration. See validate_self_enrollment.
	registration.flags.private_registration_link = True
	registration.insert(ignore_permissions=True)
	return {"status": "registered", "registration": registration.name, "event": row.name}


# --------------------------------------------------------------------- admin


def _require_admin(event: str):
	if frappe.session.user == "Guest" or not can_modify_event(event):
		frappe.throw(
			_("You do not have permission to manage registration for this event."),
			frappe.PermissionError,
		)
	if not frappe.db.exists("LMS Event", event):
		frappe.throw(_("Event not found."), frappe.DoesNotExistError)


def _link_state(event: str) -> dict:
	row = frappe.db.get_value(
		"LMS Event",
		event,
		["private_registration_enabled", "private_registration_version", "paid_event", "published"],
		as_dict=True,
	)
	enabled = bool(row.private_registration_enabled)
	return {
		"enabled": enabled,
		"url": private_link_url(event, row.private_registration_version) if enabled else None,
		"paid_event": bool(row.paid_event),
		"published": bool(row.published),
	}


@frappe.whitelist()
def get_private_link(event: str) -> dict:
	_require_admin(event)
	return _link_state(event)


@frappe.whitelist(methods=["POST"])
def set_private_link(event: str, enabled: int | str = 1, reset: int | str = 0) -> dict:
	"""Turn the link on or off, or reset it (invalidates the old link)."""
	_require_admin(event)
	enabled, reset = cint(enabled), cint(reset)
	if enabled and frappe.db.get_value("LMS Event", event, "paid_event"):
		frappe.throw(
			_(
				"Private registration links are for free or prepaid events. "
				"Turn off Paid Event first, or use a coupon for paid events."
			)
		)
	values = {"private_registration_enabled": 1 if enabled else 0}
	if reset:
		values["private_registration_version"] = (
			cint(frappe.db.get_value("LMS Event", event, "private_registration_version")) + 1
		)
	# set_value, not save(): a settings form left open in another tab must not
	# be able to overwrite these, and nothing else on the event changes.
	frappe.db.set_value("LMS Event", event, values)
	action = "reset" if reset else ("turned on" if enabled else "turned off")
	frappe.get_doc("LMS Event", event).add_comment(
		"Info", f"Private registration link {action} by {frappe.session.user}"
	)
	return _link_state(event)


@frappe.whitelist(methods=["POST"])
def register_member(event: str, member: str, payment: str | None = None) -> dict:
	"""Admin adds an existing user to an event from the Dashboard.

	Server-side so Global Admins and event instructors, who are not reliably
	covered by the LMS Event Registration permission rows, can do it too.
	The registration controller still enforces payment for paid events,
	duplicates and seat count."""
	_require_admin(event)
	if not member or not frappe.db.exists("User", member):
		frappe.throw(_("Please choose a member."))
	registration = frappe.get_doc(
		{
			"doctype": "LMS Event Registration",
			"event": event,
			"member": member,
			"member_name": frappe.db.get_value("User", member, "full_name"),
			"payment": payment or None,
		}
	)
	registration.insert(ignore_permissions=True)
	return {"status": "registered", "registration": registration.name}

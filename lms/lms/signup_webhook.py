"""Outbound webhook for new accounts, enrollments and event registrations.

Each one is POSTed as JSON to the URL in the `signup_webhook_url` site config
key (a Zapier catch hook), so marketing automation can react to it. The payload
says what was signed up for (`item_type`) and who that content is aimed at
(`audience`), which is how the receiving end tells a parent resource from an
educator one. Every event sends the same keys, blank where they do not apply.

The URL lives in site config, not in the repo: a site without the key sends
nothing, so dev and test sites stay silent unless they are pointed somewhere.

Everything here fails open. A marketing webhook must never block a signup, an
enrollment or a Stripe webhook. The POST itself runs in a background job after
the transaction commits, so a rolled-back signup sends nothing and the job
reads the row as it was finally saved.
"""

import frappe
import requests
from frappe.utils import get_url

CONFIG_KEY = "signup_webhook_url"
TIMEOUT = 10
TRAFFIC_KEYS = ("source", "medium", "campaign", "referrer")


def queue_signup_webhook(doctype, name):
	"""Schedule the webhook for a freshly created document. Never raises."""
	try:
		if not frappe.conf.get(CONFIG_KEY):
			return
		# Bulk imports, patches and installs create rows nobody signed up for.
		if frappe.flags.in_import or frappe.flags.in_migrate or frappe.flags.in_install:
			return

		frappe.enqueue(
			"lms.lms.signup_webhook.deliver",
			queue="short",
			enqueue_after_commit=True,
			source_doctype=doctype,
			source_name=name,
		)
	except Exception:
		frappe.log_error(title="Signup webhook not queued")


def deliver(source_doctype, source_name):
	"""Background job: build the payload and POST it. Never raises."""
	try:
		url = frappe.conf.get(CONFIG_KEY)
		if not url:
			return

		payload = build_payload(source_doctype, source_name)
		if not payload:
			return

		requests.post(url, json=payload, timeout=TIMEOUT).raise_for_status()
	except Exception:
		frappe.log_error(title=f"Signup webhook failed for {source_doctype} {source_name}")


def build_payload(doctype, name):
	"""Payload for one document, or None if it is gone or not ours to send."""
	builder = BUILDERS.get(doctype)
	return builder(name) if builder else None


def _url(path=""):
	"""Absolute site URL. The delivery job has no request to read the scheme
	from, so `get_url` falls back to http:// there. The sites are HTTPS-only."""
	url = get_url(path)
	return "https://" + url[len("http://") :] if url.startswith("http://") else url


def _payload(event, occurred_at, **values):
	payload = {
		"event": event,
		# Site-timezone timestamp, to the second.
		"occurred_at": str(occurred_at or "")[:19],
		"site": _url(),
		"email": "",
		"full_name": "",
		"first_name": "",
		"last_name": "",
		"phone": "",
		# The audience the member picked for their own notifications, if any.
		"user_audience": "",
		"item_type": "",
		"item_id": "",
		"item_title": "",
		"item_url": "",
		# The audience the content is aimed at.
		"audience": "",
		"resource_type": "",
		"paid": False,
		"traffic_source": "",
		"traffic_medium": "",
		"traffic_campaign": "",
		"traffic_referrer": "",
	}
	payload.update({key: value for key, value in values.items() if value is not None})
	return payload


def _member(user):
	details = (
		frappe.db.get_value(
			"User",
			user,
			["email", "full_name", "first_name", "last_name", "notification_audience"],
			as_dict=True,
		)
		or {}
	)
	return {
		"email": details.get("email") or user,
		"full_name": details.get("full_name") or "",
		"first_name": details.get("first_name") or "",
		"last_name": details.get("last_name") or "",
		"user_audience": details.get("notification_audience") or "",
	}


def _course_item(course):
	"""Resources share the LMS Course doctype, so `course_type` decides which
	one this is."""
	details = frappe.db.get_value(
		"LMS Course",
		course,
		["title", "course_type", "resource_type", "audience", "paid_course"],
		as_dict=True,
	)
	if not details:
		return {}

	is_resource = details.course_type == "Resource"
	return {
		"item_type": "Resource" if is_resource else "Course",
		"item_id": course,
		"item_title": details.title or "",
		"item_url": _url(f"/lms/{'resources' if is_resource else 'courses'}/{course}"),
		"audience": details.audience or "",
		"resource_type": details.resource_type or "",
		"paid": bool(details.paid_course),
	}


def _event_item(event):
	details = frappe.db.get_value("LMS Event", event, ["title", "audience", "paid_event"], as_dict=True)
	if not details:
		return {}

	return {
		"item_type": "Event",
		"item_id": event,
		"item_title": details.title or "",
		"item_url": _url(f"/lms/events/{event}"),
		"audience": details.audience or "",
		"paid": bool(details.paid_event),
	}


def _traffic(row, prefix="traffic_"):
	return {f"traffic_{key}": row.get(f"{prefix}{key}") or "" for key in TRAFFIC_KEYS}


def _user_payload(name):
	user = frappe.db.get_value(
		"User",
		name,
		["creation", "signup_source", "signup_source_type"]
		+ [f"signup_traffic_{key}" for key in TRAFFIC_KEYS],
		as_dict=True,
	)
	if not user:
		return None

	# The page they signed up on, when it was a course, resource or event page.
	item = {}
	if user.signup_source and user.signup_source_type in ("Course", "Resource"):
		item = _course_item(user.signup_source)
	elif user.signup_source and user.signup_source_type == "Event":
		item = _event_item(user.signup_source)

	return _payload(
		"account_signup",
		user.creation,
		**_member(name),
		**item,
		**_traffic(user, prefix="signup_traffic_"),
	)


def _enrollment_payload(name):
	enrollment = frappe.db.get_value(
		"LMS Enrollment",
		name,
		["creation", "member", "course"] + [f"traffic_{key}" for key in TRAFFIC_KEYS],
		as_dict=True,
	)
	if not enrollment:
		return None

	item = _course_item(enrollment.course)
	event = "resource_signup" if item.get("item_type") == "Resource" else "course_enrollment"
	return _payload(event, enrollment.creation, **_member(enrollment.member), **item, **_traffic(enrollment))


def _event_registration_payload(name):
	registration = frappe.db.get_value(
		"LMS Event Registration", name, ["creation", "member", "event"], as_dict=True
	)
	if not registration:
		return None

	return _payload(
		"event_registration",
		registration.creation,
		**_member(registration.member),
		**_event_item(registration.event),
	)


def _community_event_registration_payload(name):
	"""Community events are guest RSVPs, so the guardian is the contact and
	there is no User row to read."""
	registration = frappe.db.get_value(
		"Community Event Registration",
		name,
		[
			"creation",
			"parent_event",
			"guardian_name",
			"guardian_email",
			"guardian_phone",
			"donation_total",
		],
		as_dict=True,
	)
	if not registration:
		return None

	event = (
		frappe.db.get_value("Community Event", registration.parent_event, ["title", "route"], as_dict=True)
		or {}
	)
	full_name = (registration.guardian_name or "").strip()
	parts = full_name.split(None, 1)

	return _payload(
		"community_event_registration",
		registration.creation,
		email=registration.guardian_email or "",
		full_name=full_name,
		first_name=parts[0] if parts else "",
		last_name=parts[1] if len(parts) > 1 else "",
		phone=registration.guardian_phone or "",
		item_type="Community Event",
		item_id=registration.parent_event,
		item_title=event.get("title") or "",
		item_url=_url(f"/{event.get('route')}") if event.get("route") else "",
		paid=float(registration.donation_total or 0) > 0,
	)


BUILDERS = {
	"User": _user_payload,
	"LMS Enrollment": _enrollment_payload,
	"LMS Event Registration": _event_registration_payload,
	"Community Event Registration": _community_event_registration_payload,
}

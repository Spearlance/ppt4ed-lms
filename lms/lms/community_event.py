"""Community Event APIs — public RSVP + admin list/detail.

Public RSVP submits as Guest; donation > 0 routes through Stripe Checkout with
metadata `type=community_event_donation` for the webhook to finalize.
"""

import frappe
from frappe import _
from frappe.utils import cint, get_url

from lms.lms.doctype.community_event.community_event import get_confirmed_attendee_count


ADMIN_ROLES = ("System Manager", "Moderator", "Global Admin")


def _ensure_admin():
	roles = frappe.get_roles(frappe.session.user)
	if not any(r in roles for r in ADMIN_ROLES):
		frappe.throw(_("You do not have permission to manage community events."), frappe.PermissionError)


def _normalize_attendees(attendees):
	"""Accepts list of dicts (from JSON) or list of strings (legacy fallback).
	Returns a list of {attendee_name, attendee_age} dicts with whitespace-trimmed
	names and Pyints for ages."""
	if isinstance(attendees, str):
		import json
		attendees = json.loads(attendees)
	if not isinstance(attendees, list):
		frappe.throw(_("Attendees must be a list."))

	cleaned = []
	for item in attendees:
		if isinstance(item, str):
			name = item.strip()
			age = None
		elif isinstance(item, dict):
			name = (item.get("attendee_name") or item.get("name") or "").strip()
			age = item.get("attendee_age") or item.get("age")
			age = cint(age) if age not in (None, "") else None
		else:
			continue
		if name:
			cleaned.append({"attendee_name": name, "attendee_age": age})
	return cleaned


@frappe.whitelist(allow_guest=True, methods=["POST"])
def submit_rsvp(slug, guardian_name, guardian_email, attendees, guardian_phone=None):
	"""Public RSVP entry point. Returns either {"confirmed": True} for free
	registrations or {"checkout_url": "..."} for paid ones.

	Slug is the doc name (Community Event.name = slug). We re-fetch the event
	doc + price server-side; never trust client-supplied amounts.
	"""
	if not slug:
		frappe.throw(_("Event is required."))

	event = frappe.get_doc("Community Event", slug)
	if not event.published:
		frappe.throw(_("This event is not open for registration."))

	guardian_name = (guardian_name or "").strip()
	guardian_email = (guardian_email or "").strip().lower()
	if not guardian_name or not guardian_email:
		frappe.throw(_("Guardian name and email are required."))

	cleaned_attendees = _normalize_attendees(attendees)
	if not cleaned_attendees:
		frappe.throw(_("Please add at least one attendee."))

	# Capacity check on Free/Confirmed only — Pending registrations are excluded
	# so abandoned Stripe sessions don't permanently hold seats.
	if cint(event.max_attendees):
		taken = get_confirmed_attendee_count(event.name)
		if taken + len(cleaned_attendees) > cint(event.max_attendees):
			frappe.throw(_("Not enough seats remaining for this event."))

	extras = max(len(cleaned_attendees) - 1, 0)
	per_extra = float(event.additional_attendee_amount or 0)
	donation_total = round(extras * per_extra, 2)

	registration = frappe.get_doc({
		"doctype": "Community Event Registration",
		"parent_event": event.name,
		"guardian_name": guardian_name,
		"guardian_email": guardian_email,
		"guardian_phone": (guardian_phone or "").strip() or None,
		"attendees": cleaned_attendees,
		"payment_status": "Free" if donation_total <= 0 else "Pending",
	}).insert(ignore_permissions=True)

	if donation_total <= 0:
		_send_confirmation_email(registration.name)
		frappe.db.commit()
		return {"confirmed": True, "registration": registration.name}

	checkout_url = _create_stripe_checkout(event, registration, donation_total)
	frappe.db.commit()
	return {"checkout_url": checkout_url, "registration": registration.name}


def _create_stripe_checkout(event, registration, donation_total):
	from lms.lms.ceu_stripe import get_stripe

	unit_amount_cents = int(round(donation_total * 100))
	guardian_email = registration.guardian_email
	extras = max(cint(registration.attendee_count) - 1, 0)
	descriptor = f"{extras} additional attendee{'s' if extras != 1 else ''}"

	s = get_stripe()
	session = s.checkout.Session.create(
		mode="payment",
		customer_email=guardian_email,
		line_items=[{
			"price_data": {
				"currency": "usd",
				"unit_amount": unit_amount_cents,
				"product_data": {
					"name": f"Donation — {event.title}",
					"description": descriptor,
				},
			},
			"quantity": 1,
		}],
		metadata={
			"type": "community_event_donation",
			"event": event.name,
			"registration": registration.name,
			"guardian_email": guardian_email,
		},
		success_url=get_url(f"/{event.route}?status=confirmed"),
		cancel_url=get_url(f"/{event.route}?status=cancelled"),
	)
	frappe.db.set_value(
		"Community Event Registration",
		registration.name,
		"stripe_session_id",
		session.id,
	)
	return session.url


def _send_confirmation_email(registration_name: str):
	"""Sends the confirmation email. Used both for free signups and from the
	Stripe webhook after a paid signup is finalized."""
	from lms.lms.utils import lms_send_template_mail

	reg = frappe.get_doc("Community Event Registration", registration_name)
	event = frappe.get_doc("Community Event", reg.parent_event)

	args = {
		"guardian_name": reg.guardian_name,
		"event_title": event.title,
		"event_date": event.start_date,
		"event_time": event.start_time,
		"event_end_date": event.end_date,
		"event_end_time": event.end_time,
		"location": event.location,
		"virtual_link": event.virtual_link,
		"attendee_names": [a.attendee_name for a in reg.attendees],
		"attendee_count": reg.attendee_count,
		"donation_total": reg.donation_total,
		"event_url": get_url(f"/{event.route}"),
	}

	lms_send_template_mail(
		recipients=reg.guardian_email,
		default_subject=_("You're registered for {0}").format(event.title),
		jinja_template="community_event_confirmation",
		args=args,
		template_name="Community Event Confirmation",
	)


# ---------------------------------------------------------------------------
# Admin APIs (consumed by the Vue /lms admin surface)
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_community_events(filters=None, start=0, page_length=20, order_by="modified desc"):
	_ensure_admin()
	import json

	if isinstance(filters, str):
		filters = json.loads(filters)
	filters = filters or {}

	events = frappe.get_all(
		"Community Event",
		filters=filters,
		fields=[
			"name",
			"title",
			"published",
			"start_date",
			"end_date",
			"start_time",
			"location",
			"max_attendees",
			"additional_attendee_amount",
			"image",
			"route",
			"modified",
		],
		start=cint(start),
		page_length=cint(page_length),
		order_by=order_by,
	)
	for ev in events:
		ev["confirmed_attendees"] = get_confirmed_attendee_count(ev["name"])
	return events


@frappe.whitelist()
def get_community_event_registrations(event):
	_ensure_admin()
	regs = frappe.get_all(
		"Community Event Registration",
		filters={"parent_event": event},
		fields=[
			"name",
			"guardian_name",
			"guardian_email",
			"guardian_phone",
			"attendee_count",
			"donation_total",
			"payment_status",
			"registered_on",
		],
		order_by="registered_on desc",
	)
	for reg in regs:
		reg["attendees"] = frappe.get_all(
			"Community Event Attendee",
			filters={"parent": reg["name"], "parenttype": "Community Event Registration"},
			fields=["attendee_name", "attendee_age"],
			order_by="idx asc",
		)
	return regs


@frappe.whitelist()
def delete_community_event_registration(name):
	_ensure_admin()
	frappe.delete_doc("Community Event Registration", name, ignore_permissions=True)
	return {"deleted": name}

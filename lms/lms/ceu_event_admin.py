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


# ---------------------------------------------------------------------------
# CEU credit verification: in-person quiz scores and online-quiz overrides
# ---------------------------------------------------------------------------


def _require_event_scorer(event: str):
	"""Instructors of the event and LMS admins may record credit quiz results."""
	from lms.lms.utils import can_modify_event

	if not can_modify_event(event):
		frappe.throw(
			_("You do not have permission to record quiz results for this event."),
			frappe.PermissionError,
		)


def _parse_entries(entries) -> list[dict]:
	if isinstance(entries, str):
		try:
			entries = json.loads(entries)
		except ValueError:
			frappe.throw(_("Could not read the quiz results to record."))
	if isinstance(entries, dict):
		entries = [entries]
	if not isinstance(entries, (list, tuple)):
		frappe.throw(_("Could not read the quiz results to record."))
	parsed = []
	for entry in entries:
		if not isinstance(entry, dict) or not entry.get("member"):
			continue
		percentage = entry.get("percentage")
		if percentage in (None, ""):
			percentage = 100
		percentage = flt(percentage)
		if percentage < 0 or percentage > 100:
			frappe.throw(_("Scores must be between 0 and 100 (got {0}).").format(percentage))
		parsed.append(
			{
				"member": str(entry["member"]),
				"percentage": percentage,
				"note": (entry.get("note") or "").strip()[:500],
			}
		)
	return parsed


@frappe.whitelist()
def record_event_quiz_results(event: str, entries) -> dict:
	"""Record admin-entered credit quiz scores for one or more attendees.

	Used for In-Person Quiz events (the only way scores get in) and as an
	override on Online Quiz events (e.g. an attendee who failed online but
	passed a paper retake). Each entry is {member, percentage?, note?};
	percentage defaults to 100 ("mark passed"). Pass/fail is judged against
	the event's threshold (the credit quiz's passing percentage when one is
	linked, else credit_passing_percentage). A passing score mints the
	certificate immediately if the feedback survey is already in; otherwise
	the cert mints when the survey arrives. Every entry is logged as a
	comment on the event so overrides are auditable.
	"""
	from lms.lms.doctype.lms_event.lms_event import (
		get_credit_event_doc,
		get_credit_passing_percentage,
		get_credit_quiz_status,
		has_submitted_event_survey,
		maybe_auto_mint_event_certificate,
		requires_credit_quiz,
	)

	_require_event_scorer(event)

	event_doc = get_credit_event_doc(event)
	if not event_doc:
		frappe.throw(_("Event {0} not found.").format(event))
	if not requires_credit_quiz(event_doc):
		frappe.throw(
			_("This event issues credit from the feedback survey alone. Set Credit Verification to Online Quiz or In-Person Quiz in the event settings to record scores.")
		)

	parsed = _parse_entries(entries)
	if not parsed:
		frappe.throw(_("Select at least one attendee to record a score for."))

	members = [p["member"] for p in parsed]
	registered = set(
		frappe.get_all(
			"LMS Event Registration",
			filters={"event": event, "member": ["in", members]},
			pluck="member",
		)
	)
	not_registered = [m for m in members if m not in registered]
	if not_registered:
		frappe.throw(
			_("Not registered for this event: {0}").format(", ".join(not_registered))
		)

	threshold = get_credit_passing_percentage(event_doc)
	actor = frappe.session.user
	actor_name = frappe.utils.get_fullname(actor)
	event_ref = frappe.get_doc("LMS Event", event)
	recorded = []

	for entry in parsed:
		member = entry["member"]
		percentage = entry["percentage"]
		submission = frappe.get_doc(
			{
				"doctype": "LMS Quiz Submission",
				"quiz": event_doc.credit_quiz,
				"event_name": event,
				"member": member,
				"score": cint(round(percentage)),
				"score_out_of": 100,
				"percentage": cint(round(percentage)),
				"passing_percentage": cint(round(threshold)),
				"entered_by_admin": 1,
				"graded_by": actor,
				"admin_note": entry["note"],
			}
		)
		submission.insert(ignore_permissions=True)
		# score_out_of is fetch_from quiz.total_marks and the controller derives
		# percentage from score/score_out_of, so a linked quiz would skew the
		# stored numbers. Pin all three to the percentage the admin entered.
		submission.db_set(
			{
				"score": cint(round(percentage)),
				"score_out_of": 100,
				"percentage": cint(round(percentage)),
			},
			update_modified=False,
		)
		if event_doc.credit_quiz:
			submission.db_set("course", None, update_modified=False)

		passed = percentage >= threshold
		certificate = maybe_auto_mint_event_certificate(member, event) if passed else None
		member_name = frappe.utils.get_fullname(member)

		event_ref.add_comment(
			"Info",
			_("{0} recorded a credit quiz score of {1}% for {2} ({3}): {4}.{5}").format(
				actor_name,
				cint(round(percentage)),
				member_name,
				member,
				_("passed") if passed else _("did not pass"),
				f" {entry['note']}" if entry["note"] else "",
			),
		)

		recorded.append(
			{
				"member": member,
				"member_name": member_name,
				"percentage": percentage,
				"passed": passed,
				"certificate": certificate,
				"survey_submitted": has_submitted_event_survey(event_doc, member),
				"status": get_credit_quiz_status(event_doc, member),
			}
		)

	return {"recorded": recorded, "passing_percentage": threshold}


@frappe.whitelist()
def issue_event_certificates(event: str, members) -> dict:
	"""Issue the event certificate to selected attendees, by hand.

	This is how Manual events certify (after an external quiz such as a
	Google Form), and it works as an override in every other mode: no survey
	or quiz gate is checked. Attendees who already hold the certificate are
	skipped, not duplicated. Each issue is logged as a comment on the event
	so it is auditable, and the certificate email goes out as usual.

	`members` is a list of member emails (JSON string or list).
	"""
	from lms.lms.doctype.lms_event.lms_event import issue_event_certificate

	_require_event_scorer(event)

	event_doc = frappe.db.get_value(
		"LMS Event", event, ["name", "title", "certification"], as_dict=True
	)
	if not event_doc:
		frappe.throw(_("Event {0} not found.").format(event))
	if not event_doc.certification:
		frappe.throw(
			_("Turn on Certification in the event settings before issuing certificates.")
		)

	names = _parse_names(members)
	if not names:
		frappe.throw(_("Select at least one attendee to certify."))

	registered = set(
		frappe.get_all(
			"LMS Event Registration",
			filters={"event": event, "member": ["in", names]},
			pluck="member",
		)
	)
	not_registered = [m for m in names if m not in registered]
	if not_registered:
		frappe.throw(_("Not registered for this event: {0}").format(", ".join(not_registered)))

	actor_name = frappe.utils.get_fullname(frappe.session.user)
	event_ref = frappe.get_doc("LMS Event", event)
	issued, skipped = [], []

	for member in names:
		member_name = frappe.utils.get_fullname(member)
		if frappe.db.exists("LMS Certificate", {"member": member, "event_name": event}):
			skipped.append({"member": member, "member_name": member_name})
			continue
		certificate = issue_event_certificate(member, event)
		event_ref.add_comment(
			"Info",
			_("{0} issued the certificate to {1} ({2}).").format(actor_name, member_name, member),
		)
		issued.append({"member": member, "member_name": member_name, "certificate": certificate})

	return {"issued": issued, "skipped": skipped}


@frappe.whitelist()
def get_event_credit_status(event: str) -> dict:
	"""Per-attendee credit progress for the admin dashboard: survey in?,
	best quiz score, passed?, certificate issued?. Keyed by member email."""
	from lms.lms.doctype.lms_event.lms_event import (
		get_credit_event_doc,
		get_credit_passing_percentage,
		get_credit_verification,
		requires_credit_quiz,
	)

	_require_event_scorer(event)

	event_doc = get_credit_event_doc(event)
	if not event_doc:
		frappe.throw(_("Event {0} not found.").format(event))

	members = frappe.get_all(
		"LMS Event Registration", filters={"event": event}, pluck="member"
	)
	credit_quiz = event_doc.credit_quiz
	threshold = get_credit_passing_percentage(event_doc)

	survey_members = set()
	if event_doc.survey_quiz:
		survey_members = set(
			frappe.get_all(
				"LMS Quiz Submission",
				filters={"event_name": event, "quiz": event_doc.survey_quiz},
				pluck="member",
			)
		)

	certs = {
		c.member: c.name
		for c in frappe.get_all(
			"LMS Certificate", filters={"event_name": event}, fields=["member", "name"]
		)
	}

	by_member = {}
	for m in members:
		by_member[m] = {
			"survey_submitted": (not event_doc.survey_quiz) or (m in survey_members),
			"attempts": 0,
			"best_percentage": None,
			"passed": False,
			"entered_by_admin": False,
			"graded_by": None,
			"admin_note": None,
			"last_recorded": None,
			"certificate": certs.get(m),
		}

	if requires_credit_quiz(event_doc):
		rows = frappe.get_all(
			"LMS Quiz Submission",
			filters={"event_name": event, "member": ["in", members or [""]]},
			fields=[
				"member",
				"quiz",
				"percentage",
				"passing_percentage",
				"entered_by_admin",
				"graded_by",
				"admin_note",
				"creation",
			],
			order_by="creation asc",
		)
		for r in rows:
			if not (r.entered_by_admin or (credit_quiz and r.quiz == credit_quiz)):
				continue
			s = by_member.get(r.member)
			if not s:
				continue
			pct = flt(r.percentage)
			if not r.entered_by_admin:
				s["attempts"] += 1
			if s["best_percentage"] is None or pct > s["best_percentage"]:
				s["best_percentage"] = pct
			row_threshold = r.passing_percentage if r.passing_percentage is not None else threshold
			if pct >= flt(row_threshold):
				s["passed"] = True
			s["entered_by_admin"] = bool(r.entered_by_admin)
			s["graded_by"] = r.graded_by
			s["admin_note"] = r.admin_note
			s["last_recorded"] = r.creation

	return {
		"mode": get_credit_verification(event_doc),
		"credit_quiz_required": requires_credit_quiz(event_doc),
		"survey_quiz": event_doc.survey_quiz,
		"credit_quiz": credit_quiz,
		"passing_percentage": threshold,
		"members": by_member,
	}

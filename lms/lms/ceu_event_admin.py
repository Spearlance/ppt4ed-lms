"""Admin tools for managing event registrations from the LMS UI.

Staff (Moderator / System Manager / Global Admin) don't have Desk access on
prod, so anything they need to do to a roster has to live behind a whitelisted
method the Vue admin dashboard can call.
"""

import json

import frappe
from frappe import _
from frappe.utils import cint, flt, nowdate


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
		has_survey_submission,
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
				"survey_submitted": has_survey_submission(event_doc, member),
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
		is_survey_required,
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
		"survey_required": is_survey_required(event_doc),
		"survey_quiz": event_doc.survey_quiz,
		"credit_quiz": credit_quiz,
		"passing_percentage": threshold,
		"members": by_member,
	}


# --------------------------------------------------------------------------- #
# Sample certificate preview
# --------------------------------------------------------------------------- #

SAMPLE_PARTICIPANT_NAME = "Sample Participant"
SAMPLE_LICENSE_INFO = "License No. 000000 (sample)"


def _require_certificate_admin():
	from lms.lms.utils import LMS_MODERATOR_ROLES

	roles = frappe.get_roles()
	if not any(role in roles for role in LMS_MODERATOR_ROLES):
		frappe.throw(_("Only LMS admins can preview certificates."), frappe.PermissionError)


def _build_sample_certificate(event: str | None = None, course: str | None = None):
	"""An unsaved LMS Certificate for `event` or `course`, filled the way the
	earned one would be (CEU hours, disciplines, template) plus a sample
	participant. Never inserted: no certificate, credit, completion or email
	results."""
	from lms.lms.doctype.lms_certificate.lms_certificate import (
		compute_ceu_fields,
		get_default_certificate_template,
	)

	if bool(event) == bool(course):
		frappe.throw(_("Pick one course or one event to preview."))

	template = get_default_certificate_template()
	doc = frappe.new_doc("LMS Certificate")
	doc.update(
		{
			"member": frappe.session.user,
			"member_name": SAMPLE_PARTICIPANT_NAME,
			"issue_date": nowdate(),
			"template": template,
			"published": 0,
		}
	)
	if event:
		title = frappe.db.get_value("LMS Event", event, "title")
		if title is None:
			frappe.throw(_("Event {0} not found.").format(event), frappe.DoesNotExistError)
		doc.event_name = event
		doc.event_title = title
		ceu = compute_ceu_fields(event_name=event)
	else:
		title = frappe.db.get_value("LMS Course", course, "title")
		if title is None:
			frappe.throw(_("Course {0} not found.").format(course), frappe.DoesNotExistError)
		doc.course = course
		doc.course_title = title
		ceu = compute_ceu_fields(course=course)
	# printview reads doc.name for the page title and the permission check
	# looks at doc.owner; neither is persisted because the doc is never saved.
	doc.name = f"SAMPLE-{event or course}"
	doc.owner = frappe.session.user
	# Same computation as LMSCertificate.populate_ceu_fields, without the db_set.
	ceu = ceu or {"ceu_hours": None, "ceu_disciplines": ""}
	doc.ceu_hours = ceu["ceu_hours"]
	doc.ceu_disciplines = ceu["ceu_disciplines"]
	doc.license_info = SAMPLE_LICENSE_INFO
	# The print format watermarks the page and swaps in the sample name
	# when this attribute is present; the earned path never sets it.
	doc.is_sample_preview = 1
	doc.flags.is_sample_preview = True
	return doc, template


def _render_sample_html(doc, template: str) -> str:
	"""Same renderer the printview page / PDF use, minus the page chrome
	(toolbar, gutter) so it sits cleanly inside the admin preview frame."""
	from frappe.www.printview import get_print_style, get_rendered_template

	print_format = frappe.get_doc("Print Format", template)
	body = get_rendered_template(doc, print_format=print_format, no_letterhead=1)
	style = get_print_style(print_format=print_format)
	# Frappe's screen stylesheet shapes .print-format as a padded portrait
	# Letter sheet (max-width 8.3in, min-height 11.69in, 0.75in padding). The
	# certificate is a landscape 11in x 8.5in page, so pin the wrapper to it.
	fit = (
		"html,body{margin:0;padding:0;background:#fff;overflow:hidden}"
		".print-format{width:11in!important;height:8.5in!important;max-width:none!important;"
		"min-height:0!important;padding:0!important;margin:0!important;border-radius:0!important;"
		"box-shadow:none!important;overflow:hidden}"
	)
	return (
		'<!doctype html><html lang="en"><head><meta charset="utf-8">'
		"<title>Sample certificate</title>"
		f"<style>{style}</style><style>{fit}</style></head>"
		f'<body><div class="print-format">{body}</div></body></html>'
	)


def _serve_sample_pdf(doc, template: str, filename: str):
	"""PDF twin of the HTML preview (same generator as earned certificates),
	served as a download."""
	pdf_generator = frappe.db.get_value("Print Format", template, "pdf_generator") or "chrome"
	pdf = frappe.get_print(
		"LMS Certificate",
		doc.name,
		template,
		doc=doc,
		no_letterhead=1,
		as_pdf=True,
		pdf_generator=pdf_generator,
	)
	frappe.local.response.filename = filename
	frappe.local.response.filecontent = pdf
	frappe.local.response.type = "pdf"


@frappe.whitelist()
def preview_sample_certificate(course: str | None = None, event: str | None = None) -> dict:
	"""Render a course's or event's certificate as a clearly marked sample,
	through the same print format the earned certificate uses, so signers,
	credentials, title, hours, date and format can be checked before anyone
	earns one. Only the recipient differs.

	Moderators / Global Admins only. Read-only: nothing is inserted, no
	credit is awarded, no completion changes and no email is queued.
	"""
	_require_certificate_admin()
	doc, template = _build_sample_certificate(event=event, course=course)
	return {
		"html": _render_sample_html(doc, template),
		"template": template,
		"sample_name": SAMPLE_PARTICIPANT_NAME,
		"title": doc.event_title if event else doc.course_title,
		"event_title": doc.event_title if event else None,
		"course_title": doc.course_title if course else None,
	}


@frappe.whitelist()
def preview_sample_certificate_pdf(course: str | None = None, event: str | None = None):
	"""PDF twin of preview_sample_certificate, named after the course / event."""
	_require_certificate_admin()
	doc, template = _build_sample_certificate(event=event, course=course)
	_serve_sample_pdf(doc, template, f"sample-certificate-{event or course}.pdf")


@frappe.whitelist()
def preview_event_certificate(event: str) -> dict:
	"""Event-only entry point kept for existing callers; see
	preview_sample_certificate."""
	return preview_sample_certificate(event=event)


@frappe.whitelist()
def preview_event_certificate_pdf(event: str):
	"""Event-only entry point kept for existing callers; see
	preview_sample_certificate_pdf."""
	return preview_sample_certificate_pdf(event=event)


# --------------------------------------------------------------------------- #
# Signer credentials
# --------------------------------------------------------------------------- #

MAX_CREDENTIALS_LENGTH = 140


@frappe.whitelist()
def get_signer_profiles(users) -> list[dict]:
	"""Name + credentials for the selected certificate signers, so the event
	settings form can show (and let an admin fix) what will print."""
	_require_event_admin()
	names = _parse_names(users)
	if not names:
		return []
	return frappe.get_all(
		"User",
		filters={"name": ["in", names]},
		fields=["name", "full_name", "credentials"],
	)


@frappe.whitelist()
def set_signer_credentials(user: str, credentials: str = "") -> dict:
	"""Set the credentials printed after `user`'s name on certificates they
	sign. Admin-only (PPT admins have no Desk and cannot open the User form).
	Overwrites only on an explicit save; blank clears."""
	_require_event_admin()
	if not frappe.db.exists("User", user):
		frappe.throw(_("User {0} not found.").format(user))
	credentials = (credentials or "").strip()
	if len(credentials) > MAX_CREDENTIALS_LENGTH:
		frappe.throw(
			_("Credentials can be at most {0} characters.").format(MAX_CREDENTIALS_LENGTH)
		)
	frappe.db.set_value("User", user, "credentials", credentials)
	return {"user": user, "credentials": credentials}

# Copyright (c) 2022, Frappe and contributors
# For license information, please see license.txt

import base64
import json
from datetime import timedelta

import frappe
import requests
from frappe import _
from frappe.desk.doctype.notification_log.notification_log import make_notification_logs
from frappe.model.document import Document
from frappe.utils import (
	add_days,
	cint,
	format_datetime,
	get_datetime,
	get_time,
	getdate,
	now_datetime,
	nowdate,
)

from lms.lms.utils import (
	LMS_MODERATOR_ROLES,
	ensure_instructors_have_moderator_role,
	generate_slug,
	get_assignment_details,
	get_audience_recipients,
	get_instructors,
	get_lesson_index,
	get_lesson_url,
	get_lms_route,
	get_quiz_details,
	guest_access_allowed,
)


class LMSEvent(Document):
	def validate(self):
		self.derive_schedule_from_event_days()
		self.validate_seats_left()
		self.validate_event_end_date()
		self.validate_event_days()
		self.validate_duplicate_courses()
		self.validate_amount_and_currency()
		self.validate_early_bird()
		self.validate_duplicate_assessments()
		self.validate_timetable()
		self.validate_evaluation_end_date()
		self.validate_conferencing_provider()
		ensure_instructors_have_moderator_role([row.instructor for row in self.instructors or []])

	def on_update(self):
		if self.has_value_changed("published") and self.published:
			frappe.enqueue(send_notification_for_published_event, batch=self)

	def autoname(self):
		if not self.name:
			self.name = generate_slug(self.title, "LMS Event")

	def validate_event_end_date(self):
		if self.end_date < self.start_date:
			frappe.throw(_("Event end date cannot be before the event start date"))

	def validate_duplicate_courses(self):
		courses = [row.course for row in self.courses]
		duplicates = {course for course in courses if courses.count(course) > 1}
		if len(duplicates):
			title = frappe.db.get_value("LMS Course", next(iter(duplicates)), "title")
			frappe.throw(_("Course {0} has already been added to this event.").format(frappe.bold(title)))

	def validate_amount_and_currency(self):
		if self.paid_event:
			if not self.amount:
				frappe.throw(_("Amount is required for paid events."))
			# Currency is USD-only on the form; default it server-side when missing
			# so old API/import paths keep working without a currency selector.
			if not self.currency:
				self.currency = "USD"

	def derive_schedule_from_event_days(self):
		"""`event_days` is the source of truth for the schedule. The top-level
		`start_date`/`end_date`/`start_time`/`end_time` columns are derived from
		it on save and kept for filtering, listing, and email templates that
		still reference them.

		If `event_days` is empty (e.g. older API import paths), seed it from
		the legacy top-level inputs so nothing in the codebase breaks."""
		if not self.event_days and self.start_date:
			self.append("event_days", {
				"date": self.start_date,
				"start_time": self.start_time,
				"end_time": self.end_time,
			})

		if not self.event_days:
			return

		# Ascending sort: earliest date first; tiebreak by start_time so the
		# first/last row is deterministic when two days share a date.
		ordered = sorted(
			self.event_days,
			key=lambda r: (r.date, str(r.start_time or "")),
		)
		self.start_date = ordered[0].date
		self.end_date = ordered[-1].date
		self.start_time = ordered[0].start_time
		self.end_time = ordered[-1].end_time

	def validate_event_days(self):
		"""Each row needs start<end, and the date must fall within the event window."""
		for row in self.event_days or []:
			if row.start_time and row.end_time:
				if get_time(row.start_time) >= get_time(row.end_time):
					frappe.throw(
						_("Schedule Row #{0}: Start time cannot be greater than or equal to end time.").format(row.idx)
					)
			if row.date and (row.date < self.start_date or row.date > self.end_date):
				frappe.throw(
					_("Schedule Row #{0}: Date must be between the event start and end dates.").format(row.idx)
				)

	def validate_early_bird(self):
		if not self.paid_event:
			return
		# Treat 0 as "not set" so the form's blank-defaults-to-zero behavior
		# never accidentally enables an early-bird at $0.
		amount = float(self.early_bird_amount or 0)
		deadline = self.early_bird_deadline
		if amount <= 0 and not deadline:
			return
		if amount <= 0:
			frappe.throw(_("Set an early bird amount when a deadline is set."))
		if not deadline:
			frappe.throw(_("Early bird deadline is required when an early bird amount is set."))
		if self.start_date and getdate(deadline) > getdate(self.start_date):
			frappe.throw(_("Early bird deadline cannot be after the event start date."))

	def validate_duplicate_assessments(self):
		assessments = [row.assessment_name for row in self.assessment]
		for assessment in self.assessment:
			if assessments.count(assessment.assessment_name) > 1:
				title = frappe.db.get_value(assessment.assessment_type, assessment.assessment_name, "title")
				frappe.throw(
					_("Assessment {0} has already been added to this event.").format(frappe.bold(title))
				)

	def validate_evaluation_end_date(self):
		if self.evaluation_end_date and self.evaluation_end_date < self.end_date:
			frappe.throw(_("Evaluation end date cannot be less than the event end date."))

	def validate_seats_left(self):
		if cint(self.seat_count) < 0:
			frappe.throw(_("Seat count cannot be negative."))

		students = frappe.db.count("LMS Event Registration", {"event": self.name})
		if cint(self.seat_count) and cint(self.seat_count) < students:
			frappe.throw(_("There are no seats available in this event."))

	def validate_timetable(self):
		for schedule in self.timetable:
			if schedule.start_time and schedule.end_time:
				if get_time(schedule.start_time) > get_time(schedule.end_time) or get_time(
					schedule.start_time
				) == get_time(schedule.end_time):
					frappe.throw(
						_("Row #{0} Start time cannot be greater than or equal to end time.").format(
							schedule.idx
						)
					)

				if get_time(schedule.start_time) < get_time(self.start_time) or get_time(
					schedule.start_time
				) > get_time(self.end_time):
					frappe.throw(
						_("Row #{0} Start time cannot be outside the event duration.").format(schedule.idx)
					)

				if get_time(schedule.end_time) < get_time(self.start_time) or get_time(
					schedule.end_time
				) > get_time(self.end_time):
					frappe.throw(
						_("Row #{0} End time cannot be outside the event duration.").format(schedule.idx)
					)

			if schedule.date < self.start_date or schedule.date > self.end_date:
				frappe.throw(_("Row #{0} Date cannot be outside the event duration.").format(schedule.idx))

	def validate_conferencing_provider(self):
		if self.is_new() or not self.conferencing_provider:
			return

		if self.conferencing_provider == "Google Meet":
			if not self.google_meet_account:
				frappe.throw(_("Please select a Google Meet account for this event."))

			google_meet_settings = frappe.get_doc("LMS Google Meet Settings", self.google_meet_account)
			if not google_meet_settings.enabled:
				frappe.throw(
					_(
						"The selected Google Meet account is disabled. Please enable it or select another account."
					)
				)

			if not google_meet_settings.google_calendar:
				frappe.throw(
					_("The selected Google Meet account does not have a Google Calendar configured.")
				)

		elif self.conferencing_provider == "Zoom":
			if not self.zoom_account:
				frappe.throw(_("Please select a Zoom account for this event."))

def send_notification_for_published_event(batch):
	send_notification = frappe.db.get_single_value("LMS Settings", "send_notification_for_published_eventes")
	if not send_notification:
		return

	if not batch.published:
		return
	if batch.notification_sent:
		return

	if send_notification == "Email":
		send_email_notification_for_published_event(batch)
	else:
		send_system_notification_for_published_event(batch)


def send_email_notification_for_published_event(batch):
	brand_name = frappe.db.get_single_value("Website Settings", "app_name")
	brand_logo = frappe.db.get_single_value("Website Settings", "banner_image")
	subject = _("A new course has been published on {0}").format(brand_name)
	template = "published_course_notification"
	instructors = get_instructors("LMS Event", batch.name)
	students = get_audience_recipients(batch.get("audience"), extra_users=instructors)

	args = {
		"brand_logo": brand_logo,
		"brand_name": brand_name,
		"title": batch.title,
		"short_introduction": batch.description,
		"start_date": batch.start_date,
		"end_date": batch.end_date,
		"start_time": batch.start_time,
		"medium": batch.medium,
		"timezone": batch.timezone,
		"instructors": instructors,
		"batch_url": frappe.utils.get_url(get_lms_route(f"events/{batch.name}")),
	}

	from lms.lms.utils import lms_send_template_mail

	lms_send_template_mail(
		recipients=instructors,
		default_subject=subject,
		jinja_template=template,
		args=args,
		template_name="New Event Published",
		bcc=students,
	)
	frappe.db.set_value("LMS Event", batch.name, "notification_sent", 1)


def send_system_notification_for_published_event(batch):
	instructors = frappe.get_all("Course Instructor", {"parent": batch.name}, pluck="instructor")
	students = get_audience_recipients(batch.get("audience"), extra_users=instructors)
	instructor_name = (
		frappe.db.get_value("User", instructors[0], "full_name") if instructors else ""
	)
	notification = frappe._dict(
		{
			"subject": _("{0} has published a new event {1}").format(
				frappe.bold(instructor_name), frappe.bold(batch.title)
			),
			"email_content": _(
				"A new event '{0}' has been published that might interest you. Check it out!"
			).format(batch.title),
			"document_type": "LMS Event",
			"document_name": batch.name,
			"from_user": instructors[0] if instructors else None,
			"type": "Alert",
			"link": get_lms_route(f"events/{batch.name}"),
		}
	)
	make_notification_logs(notification, students)
	frappe.db.set_value("LMS Event", batch.name, "notification_sent", 1)


@frappe.whitelist()
def create_live_class(
	batch_name: str,
	zoom_account: str,
	title: str,
	duration: int,
	date: str,
	time: str,
	timezone: str,
	auto_recording: str,
	description: str = None,
):
	roles = frappe.get_roles()
	if not any(role in roles for role in LMS_MODERATOR_ROLES):
		frappe.throw(_("You do not have permission to create a live class."))

	payload = {
		"topic": title,
		"start_time": format_datetime(f"{date} {time}", "yyyy-MM-ddTHH:mm:ssZ"),
		"duration": duration,
		"agenda": description,
		"private_meeting": True,
		"auto_recording": "none" if auto_recording == "No Recording" else auto_recording.lower(),
		"timezone": timezone,
	}
	headers = {
		"Authorization": "Bearer " + authenticate(zoom_account),
		"content-type": "application/json",
	}
	response = requests.post(
		"https://api.zoom.us/v2/users/me/meetings", headers=headers, data=json.dumps(payload)
	)

	if response.status_code == 201:
		data = json.loads(response.text)
		payload.update(
			{
				"doctype": "LMS Live Class",
				"start_url": data.get("start_url"),
				"join_url": data.get("join_url"),
				"meeting_id": data.get("id"),
				"uuid": data.get("uuid"),
				"title": title,
				"host": frappe.session.user,
				"date": date,
				"time": time,
				"event_name": batch_name,
				"password": data.get("password"),
				"description": description,
				"auto_recording": auto_recording,
				"zoom_account": zoom_account,
			}
		)
		class_details = frappe.get_doc(payload)
		class_details.save()
		return class_details
	else:
		frappe.throw(_("Error creating live class. Please try again. {0}").format(response.text))


@frappe.whitelist()
def create_google_meet_live_class(
	batch_name: str,
	google_meet_account: str,
	title: str,
	duration: int,
	date: str,
	time: str,
	timezone: str,
	description: str = None,
):
	frappe.only_for(LMS_MODERATOR_ROLES)

	google_meet_settings = frappe.get_doc("LMS Google Meet Settings", google_meet_account)
	if not google_meet_settings.enabled:
		frappe.throw(_("Please enable the Google Meet account to use this feature."))

	if not google_meet_settings.google_calendar:
		frappe.throw(
			_(
				"The Google Meet account does not have a Google Calendar configured. Please set up a Google Calendar first."
			)
		)

	class_details = frappe.get_doc(
		{
			"doctype": "LMS Live Class",
			"title": title,
			"host": frappe.session.user,
			"date": date,
			"time": time,
			"duration": duration,
			"timezone": timezone,
			"description": description,
			"event_name": batch_name,
			"conferencing_provider": "Google Meet",
			"google_meet_account": google_meet_account,
		}
	)
	class_details.save()
	return class_details


def authenticate(zoom_account):
	zoom = frappe.get_doc("LMS Zoom Settings", zoom_account)
	if not zoom.enabled:
		frappe.throw(_("Please enable the zoom account to use this feature."))

	authenticate_url = (
		f"https://zoom.us/oauth/token?grant_type=account_credentials&account_id={zoom.account_id}"
	)

	headers = {
		"Authorization": "Basic "
		+ base64.b64encode(
			bytes(
				zoom.client_id + ":" + zoom.get_password(fieldname="client_secret", raise_exception=False),
				encoding="utf8",
			)
		).decode()
	}
	response = requests.request("POST", authenticate_url, headers=headers)
	return response.json()["access_token"]


@frappe.whitelist()
def get_event_timetable(batch: str):
	roles = frappe.get_roles()
	is_batch_student = frappe.db.exists(
		"LMS Event Registration", {"event": batch, "member": frappe.session.user}
	)
	is_admin = "Moderator" in roles or "Moderator" in roles
	if not (is_batch_student or is_admin):
		frappe.throw(
			_("You do not have permission to access announcements for this event."), frappe.PermissionError
		)

	timetable = frappe.get_all(
		"LMS Batch Timetable",
		filters={"parent": batch},
		fields=[
			"reference_doctype",
			"reference_docname",
			"date",
			"start_time",
			"end_time",
			"milestone",
			"name",
			"idx",
			"parent",
		],
		order_by="date",
	)

	show_live_class = frappe.db.get_value("LMS Event", batch, "show_live_class")
	if show_live_class:
		live_classes = get_live_classes(batch)
		timetable.extend(live_classes)

	timetable = get_timetable_details(timetable)
	return timetable


def get_live_classes(batch):
	live_classes = frappe.get_all(
		"LMS Live Class",
		{"event_name": batch},
		["name", "title", "date", "time as start_time", "duration", "join_url as url"],
		order_by="date",
	)
	for class_ in live_classes:
		class_.end_time = class_.start_time + timedelta(minutes=class_.duration)
		class_.reference_doctype = "LMS Live Class"
		class_.reference_docname = class_.name
		class_.icon = "icon-call"

	return live_classes


def get_timetable_details(timetable):
	for entry in timetable:
		entry.title = frappe.db.get_value(entry.reference_doctype, entry.reference_docname, "title")
		assessment = frappe._dict({"assessment_name": entry.reference_docname})

		if entry.reference_doctype == "Course Lesson":
			course = frappe.db.get_value(entry.reference_doctype, entry.reference_docname, "course")
			entry.url = get_lesson_url(course, get_lesson_index(entry.reference_docname))

			entry.completed = (
				True
				if frappe.db.exists(
					"LMS Course Progress",
					{
						"lesson": entry.reference_docname,
						"member": frappe.session.user,
						"status": "Complete",
					},
				)
				else False
			)

		elif entry.reference_doctype == "LMS Quiz":
			entry.url = "/quizzes"
			details = get_quiz_details(assessment, frappe.session.user)
			entry.update(details)

		elif entry.reference_doctype == "LMS Assignment":
			details = get_assignment_details(assessment, frappe.session.user)
			entry.update(details)

	timetable = sorted(timetable, key=lambda k: k["date"])
	return timetable


def send_event_start_reminder():
	events = frappe.get_all(
		"LMS Event",
		{"start_date": add_days(nowdate(), 1), "published": 1},
		["name", "title", "start_date", "start_time", "medium", "zoom_link"],
	)

	for event in events:
		students = frappe.get_all("LMS Event Registration", {"event": event.name}, ["member", "member_name"])
		for student in students:
			send_mail(event, student)


def send_mail(event, student):
	from lms.lms.utils import lms_send_template_mail

	subject = _("Your event {0} is starting tomorrow").format(event.title)

	args = {
		"student_name": student.member_name,
		"title": event.title,
		"start_date": event.start_date,
		"start_time": event.start_time,
		"date": event.start_date,
		"time": event.start_time,
		"medium": event.medium,
		"name": event.name,
		"zoom_link": event.zoom_link,
	}

	lms_send_template_mail(
		recipients=student.member,
		default_subject=subject,
		jinja_template="live_class_reminder",
		args=args,
		template_name="Event Starting Tomorrow",
		header=[_(f"Event Start Reminder: {event.title}"), "orange"],
	)


ONE_HOUR_REMINDER_WINDOW_MINUTES = 75


def send_event_one_hour_reminder():
	"""Hourly. Email enrolled members ~1 hour before their event starts.
	Looks at LMS Event Day rows so multi-day events trigger per day.
	Cache-based dedup keyed on (event, member, day) prevents the next
	hourly run from re-sending while a webinar's start time is still in
	the look-ahead window."""
	now = now_datetime()
	today = getdate()
	horizon = now + timedelta(minutes=ONE_HOUR_REMINDER_WINDOW_MINUTES)

	upcoming_days = frappe.get_all(
		"LMS Event Day",
		filters={"date": today, "parenttype": "LMS Event"},
		fields=["parent", "date", "start_time"],
	)

	for day in upcoming_days:
		try:
			start_dt = get_datetime(f"{day.date} {day.start_time}")
		except Exception:
			continue
		if not (now <= start_dt <= horizon):
			continue

		event = frappe.db.get_value(
			"LMS Event",
			day.parent,
			["name", "title", "medium", "zoom_link", "published"],
			as_dict=True,
		)
		if not event or not event.published or not event.zoom_link:
			continue

		event.start_date = day.date
		event.start_time = day.start_time

		students = frappe.get_all(
			"LMS Event Registration",
			{"event": event.name},
			["member", "member_name"],
		)
		for student in students:
			cache_key = f"event_1h_reminder:{event.name}:{student.member}:{day.date}"
			if frappe.cache().get_value(cache_key):
				continue
			send_starting_soon_mail(event, student)
			frappe.cache().set_value(cache_key, 1, expires_in_sec=86400)


def send_starting_soon_mail(event, student):
	from lms.lms.utils import lms_send_template_mail

	subject = _("Your event {0} starts in about an hour").format(event.title)

	args = {
		"student_name": student.member_name,
		"title": event.title,
		"start_date": event.start_date,
		"start_time": event.start_time,
		"date": event.start_date,
		"time": event.start_time,
		"medium": event.medium,
		"name": event.name,
		"zoom_link": event.zoom_link,
	}

	lms_send_template_mail(
		recipients=student.member,
		default_subject=subject,
		jinja_template="event_starting_soon",
		args=args,
		template_name="Event Starting in One Hour",
		header=[_(f"Starting Soon: {event.title}"), "blue"],
	)


def maybe_auto_mint_event_certificate(member, event):
	"""Mint an event certificate for `member` if one doesn't already exist.

	Caller is expected to have just recorded a survey submission. We re-check
	the survey gate here so the helper is safe to call from any path.
	Returns the new certificate name, or None if not minted.
	"""
	event_doc = frappe.db.get_value(
		"LMS Event",
		event,
		["name", "title", "certification", "survey_quiz"],
		as_dict=True,
	)
	if not event_doc or not event_doc.certification:
		return None

	if frappe.db.exists("LMS Certificate", {"member": member, "event_name": event}):
		return None

	if event_doc.survey_quiz and not frappe.db.exists(
		"LMS Quiz Submission",
		{"event_name": event, "member": member, "quiz": event_doc.survey_quiz},
	):
		return None

	template = frappe.db.get_value(
		"Property Setter",
		{"doc_type": "LMS Certificate", "property": "default_print_format"},
		"value",
	) or frappe.db.get_value("Print Format", {"doc_type": "LMS Certificate"})

	cert = frappe.get_doc(
		{
			"doctype": "LMS Certificate",
			"member": member,
			"event_name": event,
			"issue_date": nowdate(),
			"template": template,
		}
	)
	cert.insert(ignore_permissions=True)
	return cert.name


def send_event_survey_open_announcements():
	"""Hourly. For each certified event whose survey window has opened
	(now >= last event_day.end_time - SURVEY_OPEN_OFFSET_MINUTES) and whose
	survey announcement has not yet been sent, fire an announcement pointing
	students at the survey, then flip the dedup flag.

	Hourly (not daily) so the email/in-app announcement lands close to when
	the QR-code-on-slides window actually opens — presenters who end early
	want attendees to see the announcement around the same time."""
	from lms.lms.utils import SURVEY_OPEN_OFFSET_MINUTES

	now = now_datetime()

	events = frappe.get_all(
		"LMS Event",
		filters={
			"published": 1,
			"certification": 1,
			"survey_announcement_sent": 0,
		},
		fields=["name", "title", "end_date", "end_time", "survey_quiz"],
	)

	for event in events:
		if not event.survey_quiz:
			continue

		days = frappe.get_all(
			"LMS Event Day",
			filters={"parent": event.name, "parenttype": "LMS Event"},
			fields=["date", "end_time"],
			order_by="idx desc",
		)
		if days:
			last_day = days[0]
			date_str, time_str = last_day["date"], last_day["end_time"]
		else:
			date_str, time_str = event.end_date, event.end_time

		if not date_str or not time_str:
			continue
		try:
			end_dt = get_datetime(f"{date_str} {time_str}")
		except Exception:
			continue
		if now < end_dt - timedelta(minutes=SURVEY_OPEN_OFFSET_MINUTES):
			continue

		try:
			_send_survey_open_announcement(event.name, event.title)
		except Exception:
			frappe.log_error(
				frappe.get_traceback(),
				f"send_event_survey_open_announcements failed for {event.name}",
			)
			continue

		frappe.db.set_value(
			"LMS Event", event.name, "survey_announcement_sent", 1, update_modified=False
		)


def _send_survey_open_announcement(event, event_title):
	"""Post a system announcement that the event survey is now open."""
	from lms.lms.api import _fan_out_event_announcement

	students = frappe.get_all(
		"LMS Event Registration", {"event": event}, pluck="member"
	)
	if not students:
		return

	subject = _("Your feedback survey for {0} is now open").format(event_title)
	event_url = frappe.utils.get_url(get_lms_route(f"events/{event}"))
	body = _(
		"Thanks for joining {0}. Your feedback survey is now available — submitting it "
		"will issue your certificate. Visit the event page to take it: {1}"
	).format(event_title, event_url)

	sender = frappe.session.user if frappe.session.user != "Guest" else "Administrator"
	sender_email = frappe.db.get_value("User", sender, "email") or sender
	sender_full_name = frappe.db.get_value("User", sender, "full_name") or sender

	communication = frappe.get_doc(
		{
			"doctype": "Communication",
			"communication_type": "Communication",
			"communication_medium": "Email",
			"sent_or_received": "Sent",
			"subject": subject,
			"content": body,
			"sender": sender,
			"sender_full_name": sender_full_name,
			"recipients": sender_email,
			"reference_doctype": "LMS Event",
			"reference_name": event,
			"communication_date": now_datetime(),
		}
	)
	communication.flags.ignore_permissions = True
	communication.insert()

	_fan_out_event_announcement(
		event=event,
		event_title=event_title,
		subject=subject,
		body=body,
		sender=sender,
		sender_email=sender_email,
		sender_full_name=sender_full_name,
		students=students,
	)


def has_permission(doc, ptype="read", user=None):
	user = user or frappe.session.user
	if user == "Guest" and not guest_access_allowed():
		return False

	roles = frappe.get_roles(user)
	if "Moderator" in roles or "Moderator" in roles:
		return True

	if ptype not in ("read", "select", "print"):
		return False

	is_enrolled = frappe.db.exists("LMS Event Registration", {"event": doc.name, "member": user})
	if is_enrolled:
		return True

	is_batch_published = frappe.db.get_value("LMS Event", doc.name, "published")
	if is_batch_published:
		return True

	return False

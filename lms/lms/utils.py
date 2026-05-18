import hashlib
import json
import re
from datetime import timedelta

import frappe
import requests
from frappe import _
from frappe.desk.doctype.dashboard_chart.dashboard_chart import get_result
from frappe.desk.doctype.notification_log.notification_log import make_notification_logs
from frappe.desk.notifications import extract_mentions
from frappe.model.document import Document
from frappe.rate_limiter import rate_limit
from frappe.utils import (
	add_months,
	cint,
	flt,
	fmt_money,
	format_datetime,
	get_datetime,
	get_frappe_version,
	get_fullname,
	getdate,
	now_datetime,
	nowtime,
	pretty_date,
	rounded,
)
from pypika import Case
from pypika import functions as fn

from lms.lms.doctype.lms_enrollment.lms_enrollment import update_program_progress
from lms.lms.md import find_macros

RE_SLUG_NOTALLOWED = re.compile("[^a-z0-9]+")
LMS_ROLES = ["Moderator", "LMS Student"]
LMS_MODERATOR_ROLES = ["Moderator", "System Manager", "Global Admin"]


def get_lms_path():
	path = frappe.conf.get("lms_path") or "lms"
	return path.strip("/")


def get_lms_route(path=""):
	base = f"/{get_lms_path()}"
	if not path:
		return base
	return f"{base}/{path.lstrip('/')}"


def extend_bootinfo(bootinfo: dict):
	bootinfo["lms_path"] = get_lms_path()


def slugify(title: str, used_slugs: list = None):
	"""Converts title to a slug.

	If a list of used slugs is specified, it will make sure the generated slug
	is not one of them.

		>>> slugify("Hello World!")
		'hello-world'
		>>> slugify("Hello World!", ["hello-world"])
		'hello-world-2'
		>>> slugify("Hello World!", ["hello-world", "hello-world-2"])
		'hello-world-3'
	"""
	if not used_slugs:
		used_slugs = []

	slug = RE_SLUG_NOTALLOWED.sub("-", title.lower()).strip("-")
	used_slugs = set(used_slugs)

	if slug not in used_slugs:
		return slug

	count = 2
	while True:
		new_slug = f"{slug}-{count}"
		if new_slug not in used_slugs:
			return new_slug
		count = count + 1


def generate_slug(title: str, doctype: str):
	result = frappe.get_all(doctype, fields=["name"])
	slugs = {row["name"] for row in result}
	return slugify(title, used_slugs=slugs)


def get_membership(course: str, member: str = None):
	if not member:
		member = frappe.session.user

	filters = {"member": member, "course": course}

	if frappe.db.exists("LMS Enrollment", filters):
		membership = frappe.db.get_value(
			"LMS Enrollment",
			filters,
			[
				"name",
				"current_lesson",
				"progress",
				"member",
				"course",
				"certificate",
			],
			as_dict=True,
		)
		return membership

	return False


def get_chapters(course: str):
	"""Returns all chapters of this course."""
	if not course:
		return []
	chapters = frappe.get_all("Chapter Reference", {"parent": course}, ["idx", "chapter"], order_by="idx")
	for chapter in chapters:
		chapter_details = frappe.db.get_value(
			"Course Chapter",
			{"name": chapter.chapter},
			["name", "title"],
			as_dict=True,
		)
		chapter.update(chapter_details)
	return chapters


def get_lessons(course: str, chapter: str = None, get_details: bool = True, progress: bool = False):
	"""If chapter is passed, returns lessons of only that chapter.
	Else returns lessons of all chapters of the course"""
	lessons = []
	lesson_count = 0
	if chapter:
		if get_details:
			return get_lesson_details(chapter, progress=progress)
		else:
			return frappe.db.count("Lesson Reference", {"parent": chapter.name})

	for chapter in get_chapters(course):
		if get_details:
			lessons += get_lesson_details(chapter, progress=progress)
		else:
			lesson_count += frappe.db.count("Lesson Reference", {"parent": chapter.name})

	return lessons if get_details else lesson_count


def get_lesson_details(chapter: dict, progress: bool = False):
	lessons = []
	lesson_list = frappe.get_all(
		"Lesson Reference", {"parent": chapter.name}, ["lesson", "idx"], order_by="idx"
	)
	for row in lesson_list:
		lesson_details = frappe.db.get_value(
			"Course Lesson",
			row.lesson,
			[
				"name",
				"title",
				"include_in_preview",
				"body",
				"creation",
				"youtube",
				"quiz_id",
				"question",
				"file_type",
				"instructor_notes",
				"course",
				"chapter",
				"content",
			],
			as_dict=True,
		)
		lesson_details.number = f"{chapter.idx}-{row.idx}"
		lesson_details.icon = get_lesson_icon(lesson_details.body, lesson_details.content)

		if progress:
			lesson_details.is_complete = get_progress(lesson_details.course, lesson_details.name)

		lessons.append(lesson_details)
	return lessons


def get_lesson_icon(body: str, content: str):
	if content:
		content = json.loads(content)

		for block in content.get("blocks"):
			if block.get("type") == "upload" and block.get("data").get("file_type").lower() in [
				"mp4",
				"webm",
				"ogg",
				"mov",
			]:
				return "icon-youtube"

			if block.get("type") == "embed" and block.get("data").get("service") in [
				"youtube",
				"vimeo",
				"cloudflareStream",
				"bunnyStream",
			]:
				return "icon-youtube"

			if block.get("type") == "quiz":
				return "icon-quiz"
			if block.get("type") == "assignment":
				return "icon-assignment"
			if block.get("type") == "program":
				return "icon-code"

		return "icon-list"

	macros = find_macros(body)
	for macro in macros:
		if macro[0] == "YouTubeVideo" or macro[0] == "Video":
			return "icon-youtube"
		elif macro[0] == "Quiz":
			return "icon-quiz"

	return "icon-list"


def get_instructors(doctype: str, docname: str):
	instructor_details = []
	instructors = frappe.get_all(
		"Course Instructor",
		{"parent": docname, "parenttype": doctype},
		order_by="idx",
		pluck="instructor",
	)

	for instructor in instructors:
		instructor_details.append(
			frappe.db.get_value(
				"User",
				instructor,
				["name", "username", "full_name", "user_image", "first_name", "bio"],
				as_dict=True,
			)
		)
	return instructor_details


def get_average_rating(course: str):
	ratings = [review.rating for review in get_reviews(course)]
	if not len(ratings):
		return None
	return sum(ratings) / len(ratings)


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=500, seconds=60 * 60)
def get_reviews(course: str):
	reviews = frappe.get_all(
		"LMS Course Review",
		{"course": course},
		["review", "rating", "owner", "creation"],
		order_by="creation desc",
	)

	out_of_ratings = frappe.db.get_all(
		"DocField", {"parent": "LMS Course Review", "fieldtype": "Rating"}, ["options"]
	)
	out_of_ratings = (len(out_of_ratings) and out_of_ratings[0].options) or 5
	for review in reviews:
		review.rating = review.rating * out_of_ratings
		review.owner_details = frappe.db.get_value(
			"User", review.owner, ["username", "full_name", "user_image"], as_dict=True
		)
		review.creation = pretty_date(review.creation)

	return reviews


def get_lesson_index(lesson_name: str) -> str:
	"""Returns the {chapter_index}.{lesson_index} for the lesson."""
	lesson = frappe.db.get_value("Lesson Reference", {"lesson": lesson_name}, ["idx", "parent"], as_dict=True)
	if not lesson:
		return "1-1"

	chapter = frappe.db.get_value("Chapter Reference", {"chapter": lesson.parent}, ["idx"], as_dict=True)
	if not chapter:
		return "1-1"

	return f"{chapter.idx}-{lesson.idx}"


def get_lesson_url(course: str, lesson_number: str):
	if not lesson_number:
		return
	return get_lms_route(f"courses/{course}/learn/{lesson_number}")


def get_progress(course: str, lesson: str, member: str = None):
	if not member:
		member = frappe.session.user

	return frappe.db.exists(
		"LMS Course Progress",
		{"course": course, "member": member, "lesson": lesson, "status": "Complete"},
		["status"],
	)


def get_course_progress(course: str, member: str = None):
	"""Returns the course progress of the session user"""
	lesson_count = get_lessons(course, get_details=False)
	if not lesson_count:
		return 0
	completed_lessons = frappe.db.count(
		"LMS Course Progress",
		{"course": course, "member": member or frappe.session.user, "status": "Complete"},
	)
	precision = cint(frappe.db.get_default("float_precision")) or 3
	return flt(((completed_lessons / lesson_count) * 100), precision)


def is_instructor(course: str) -> bool:
	instructors = get_instructors("LMS Course", course)
	for instructor in instructors:
		if instructor.name == frappe.session.user:
			return True
	return False


def has_moderator_role(member: str = None):
	roles = frappe.get_roles(member or frappe.session.user)
	return "Moderator" in roles or "System Manager" in roles


def ensure_instructors_have_moderator_role(instructor_users):
	"""Grant the Moderator role to any instructor user that doesn't have it.

	Called from LMS Course / LMS Event validate so that any path that adds
	an instructor (form, import, programmatic) leaves the user findable in
	`search_users_by_role` and able to edit their course in the frontend
	(which gates on `is_moderator`). Inserts Has Role rows directly to
	avoid User.save() side effects (no welcome / password reset email).
	"""
	users = {u for u in instructor_users if u}
	if not users:
		return

	already_have = set(
		frappe.get_all(
			"Has Role",
			filters={"parenttype": "User", "parent": ["in", list(users)], "role": "Moderator"},
			pluck="parent",
		)
	)

	for user in users - already_have:
		if not frappe.db.exists("User", user):
			continue
		role = frappe.new_doc("Has Role")
		role.parent = user
		role.parenttype = "User"
		role.parentfield = "roles"
		role.role = "Moderator"
		role.insert(ignore_permissions=True)
		frappe.clear_cache(user=user)


def is_lms_admin(member: str = None):
	"""True if the user has System Manager or Global Admin.

	Use this to gate LMS-wide admin surfaces (Stats, Admin Reports, content
	authoring shortcuts) where we want both Garrett (System Manager) and PPT
	staff (Global Admin) to have access. For dev-adjacent surfaces — Data
	Import, Role editing, payment-gateway secrets — keep using
	`frappe.only_for("System Manager")` directly.
	"""
	roles = frappe.get_roles(member or frappe.session.user)
	return "System Manager" in roles or "Global Admin" in roles


def has_student_role(member: str = None):
	return frappe.db.get_value(
		"Has Role",
		{"parent": member or frappe.session.user, "role": "LMS Student"},
		"name",
	)


def get_courses_under_review():
	return frappe.get_all(
		"LMS Course",
		{"status": "Under Review"},
		[
			"name",
			"upcoming",
			"title",
			"short_introduction",
			"image",
			"paid_course",
			"course_price",
			"currency",
			"status",
			"published",
		],
	)


def validate_image(path: str) -> str:
	if path and "/private" in path:
		frappe.db.set_value(
			"File",
			{"file_url": path},
			"is_private",
			0,
		)
		return path.replace("/private", "")
	return path


def handle_notifications(doc: Document, method: str):
	topic = frappe.db.get_value(
		"Discussion Topic",
		doc.topic,
		["reference_doctype", "reference_docname", "owner", "title"],
		as_dict=1,
	)
	if topic.reference_doctype not in ["Course Lesson", "LMS Event"]:
		return
	create_notification_log(doc, topic)
	notify_mentions_on_portal(doc, topic)
	notify_mentions_via_email(doc, topic)


def get_course_details_for_notification(topic: dict):
	users = []
	course = frappe.db.get_value("Course Lesson", topic.reference_docname, "course")
	course_title = frappe.db.get_value("LMS Course", course, "title")
	instructors = frappe.db.get_all(
		"Course Instructor", {"parent": course, "parenttype": "LMS Course"}, pluck="instructor"
	)

	users.append(topic.owner)
	users += instructors

	subject = _("New reply on the topic {0} in course {1}").format(topic.title, course_title)
	link = get_lesson_url(course, get_lesson_index(topic.reference_docname))

	return subject, link, users


def get_event_details_for_notification(topic: dict):
	users = []
	event_title = frappe.db.get_value("LMS Event", topic.reference_docname, "title")
	subject = _("New comment in event {0}").format(event_title)
	link = get_lms_route(f"events/{topic.reference_docname}#discussions")
	instructors = frappe.db.get_all(
		"Course Instructor",
		{"parenttype": "LMS Event", "parent": topic.reference_docname},
		pluck="instructor",
	)
	students = frappe.db.get_all("LMS Event Registration", {"event": topic.reference_docname}, pluck="member")
	users += instructors
	users += students
	return subject, link, users


def create_notification_log(doc: Document, topic: dict):
	if topic.reference_doctype == "Course Lesson":
		subject, link, users = get_course_details_for_notification(topic)
	else:
		subject, link, users = get_event_details_for_notification(topic)

	if doc.owner in users:
		users.remove(doc.owner)

	notification = frappe._dict(
		{
			"subject": subject,
			"email_content": doc.reply,
			"document_type": topic.reference_doctype,
			"document_name": topic.reference_docname,
			"from_user": doc.owner,
			"type": "Alert",
			"link": link,
		}
	)

	make_notification_logs(notification, users)


def notify_mentions_on_portal(doc: Document, topic: dict):
	mentions = extract_mentions(doc.reply)
	if not mentions:
		return

	from_user_name = get_fullname(doc.owner)

	if topic.reference_doctype == "Course Lesson":
		course = frappe.db.get_value("Course Lesson", topic.reference_docname, "course")
		subject = _("{0} mentioned you in a comment in {1}").format(
			frappe.bold(from_user_name), frappe.bold(topic.title)
		)
		link = get_lesson_url(course, get_lesson_index(topic.reference_docname))
	else:
		event_title = frappe.db.get_value("LMS Event", topic.reference_docname, "title")
		subject = _("{0} mentioned you in a comment in {1}").format(
			frappe.bold(from_user_name), frappe.bold(event_title)
		)
		link = get_lms_route(f"events/{topic.reference_docname}#discussions")

	for user in mentions:
		notification = frappe._dict(
			{
				"subject": subject,
				"email_content": doc.reply,
				"document_type": topic.reference_doctype,
				"document_name": topic.reference_docname,
				"for_user": user,
				"from_user": doc.owner,
				"type": "Mention",
				"link": link,
			}
		)
		make_notification_logs(notification, user)


def _render_brand_email(inner_html):
	"""Wrap pre-rendered inner HTML in the shared PPT4Ed brand shell.

	The wrapper supplies the logo header, brand-color accent band, and footer
	(contact + policy links + copyright) so individual Email Template / Jinja
	bodies stay focused on copy. Brand context is resolved here so callsites
	don't need to know about it.
	"""
	from frappe.utils import get_url

	wrapper_args = {
		"inner_html": inner_html,
		"brand_logo_url": get_url("/assets/lms/images/ppt4ed-logo.png"),
		"brand_name": frappe.db.get_single_value("Website Settings", "app_name") or "PPT4ed",
		"site_url": get_url(),
		"support_email": "support@ppt4ed.org",
		"current_year": now_datetime().year,
	}
	return frappe.render_template("templates/emails/_brand_wrapper.html", wrapper_args)


def lms_send_template_mail(
	*,
	recipients,
	default_subject,
	jinja_template,
	args,
	template_name,
	**sendmail_kwargs,
):
	"""frappe.sendmail wrapper that prefers an Email Template doctype record.

	When an Email Template named `template_name` exists, render its subject and
	body through it so admins can edit copy via /lms Settings → Email Templates
	without a deploy. Otherwise fall back to the Jinja file `jinja_template`.
	Either way the rendered body is wrapped in the shared PPT4Ed brand shell
	so chrome lives in one place. All other frappe.sendmail kwargs (header,
	retry, bcc, cc, attachments...) pass through unchanged.
	"""
	from frappe.email.doctype.email_template.email_template import get_email_template
	from frappe.utils.jinja import get_email_from_template

	if template_name and frappe.db.exists("Email Template", template_name):
		rendered = get_email_template(template_name, args)
		subject = rendered.get("subject") or default_subject
		inner_html = rendered.get("message") or ""
	else:
		inner_html, _text = get_email_from_template(jinja_template, args)
		subject = default_subject

	frappe.sendmail(
		recipients=recipients,
		subject=subject,
		content=_render_brand_email(inner_html),
		args=args,
		**sendmail_kwargs,
	)


def notify_mentions_via_email(doc: Document, topic: dict):
	outgoing_email_account = frappe.get_cached_value(
		"Email Account", {"default_outgoing": 1, "enable_outgoing": 1}, "name"
	)
	if not outgoing_email_account or not frappe.conf.get("mail_login"):
		return

	mentions = extract_mentions(doc.reply)
	if not mentions:
		return

	sender_fullname = get_fullname(doc.owner)
	recipients = [
		frappe.db.get_value(
			"User",
			{"enabled": 1, "name": name},
			"email",
		)
		for name in mentions
	]
	subject = _("{0} mentioned you in a comment").format(sender_fullname)

	if topic.reference_doctype == "LMS Event":
		link = f"/events/{topic.reference_docname}#discussions"
	if topic.reference_doctype == "Course Lesson":
		course = frappe.db.get_value("Course Lesson", topic.reference_docname, "course")
		lesson_index = get_lesson_index(topic.reference_docname)
		link = get_lesson_url(course, lesson_index)

	args = {
		"sender": sender_fullname,
		"content": doc.reply,
		"link": link,
	}

	for recipient in recipients:
		lms_send_template_mail(
			recipients=recipient,
			default_subject=subject,
			jinja_template="mention_template",
			args=args,
			template_name="Mention Notification",
			header=[subject, "green"],
			retry=3,
		)


def get_lesson_count(course: str) -> int:
	lesson_count = 0
	chapters = frappe.get_all("Chapter Reference", {"parent": course}, ["chapter"])
	for chapter in chapters:
		lesson_count += frappe.db.count("Lesson Reference", {"parent": chapter.chapter})

	return lesson_count


@frappe.whitelist()
@rate_limit(limit=500, seconds=60 * 60)
def get_chart_data(
	chart_name: str,
	timegrain: str = "Daily",
	from_date: str = None,
	to_date: str = None,
):
	frappe.only_for(["System Manager", "Global Admin"])
	from_date, to_date = get_chart_date_range(from_date, to_date)
	chart = frappe.get_doc("Dashboard Chart", chart_name)
	doctype = chart.document_type
	datefield = chart.based_on
	value_field = chart.value_based_on or "1"

	data = get_chart_details(doctype, datefield, value_field, chart, from_date, to_date)
	result = get_result(data, timegrain, from_date, to_date, chart.chart_type)
	data = []
	for row in result:
		data.append(
			{
				"date": row[0],
				"count": row[1],
			}
		)
	return data


def get_chart_date_range(from_date: str, to_date: str):
	if not from_date:
		from_date = add_months(getdate(), -1)
	if not to_date:
		to_date = getdate()

	from_date = get_datetime(from_date).strftime("%Y-%m-%d")
	to_date = get_datetime(to_date)

	return from_date, to_date


def get_chart_filters(doctype: str, chart: object, datefield: str, from_date: str, to_date: str):
	version = get_frappe_version()
	if version.startswith("15.") or version.startswith("14."):
		filters = [([chart.document_type, "docstatus", "<", 2, False])]
		filters = filters + json.loads(chart.filters_json)
		filters.append([doctype, datefield, ">=", from_date, False])
		filters.append([doctype, datefield, "<=", to_date, False])
	else:
		filters = [([chart.document_type, "docstatus", "<", 2])]
		filters = filters + json.loads(chart.filters_json)
		filters.append([doctype, datefield, ">=", from_date])
		filters.append([doctype, datefield, "<=", to_date])

	return filters


def get_chart_details(
	doctype: str, datefield: str, value_field: str, chart: object, from_date: str, to_date: str
):
	filters = get_chart_filters(doctype, chart, datefield, from_date, to_date)
	version = get_frappe_version()
	if version.startswith("15.") or version.startswith("14."):
		return frappe.db.get_all(
			doctype,
			fields=[f"{datefield} as _unit", f"SUM({value_field})", "COUNT(*)"],
			filters=filters,
			group_by="_unit",
			order_by="_unit asc",
			as_list=True,
		)
	else:
		return frappe.db.get_all(
			doctype,
			fields=[datefield, {"SUM": value_field}, {"COUNT": "*"}],
			filters=filters,
			group_by=datefield,
			order_by=datefield,
			as_list=True,
		)


@frappe.whitelist()
@rate_limit(limit=500, seconds=60 * 60)
def get_course_completion_data():
	frappe.only_for(["System Manager", "Global Admin"])
	all_membership = frappe.db.count("LMS Enrollment")
	completed = frappe.db.count("LMS Enrollment", {"progress": ["like", "%100%"]})

	return [
		{"label": "Completed", "value": completed},
		{"label": "In Progress", "value": all_membership - completed},
	]


def get_evaluator(course: str, batch: str = None):
	evaluator = None
	if batch:
		evaluator = frappe.db.get_value(
			"Batch Course",
			{"parent": batch, "course": course},
			"evaluator",
		)
	else:
		evaluator = frappe.db.get_value("LMS Course", course, "evaluator")
	return evaluator


def check_multicurrency(amount: float, currency: str, country: str = None, amount_usd: float = None):
	settings = frappe.get_single("LMS Settings")
	show_usd_equivalent = settings.show_usd_equivalent

	# Countries for which currency should not be converted
	exception_country = settings.exception_country
	exception_country = [country.country for country in exception_country]

	# Get users country
	if not country:
		country = frappe.db.get_value("Address", {"email_id": frappe.session.user}, "country")

	if not country:
		country = frappe.db.get_value("User", frappe.session.user, "country")

	if not country:
		country = get_country_code()

	# If the country is the one for which conversion is not needed then return as is
	if not country or (exception_country and country in exception_country):
		return amount, currency

	# If conversion is disabled from settings or the currency is already USD then return as is
	if not show_usd_equivalent or currency == "USD":
		return amount, currency

	# If Explicit USD price is given then return that without conversion
	if amount_usd and country and country not in exception_country:
		return amount_usd, "USD"

	# Conversion logic starts here. Exchange rate is fetched and amount is converted.
	exchange_rate = get_current_exchange_rate(currency, "USD")
	amount = flt(amount * exchange_rate, 2)
	currency = "USD"

	# Check if the amount should be rounded and then apply rounding
	apply_rounding = settings.apply_rounding
	if apply_rounding and amount % 100 != 0:
		amount = amount + 100 - amount % 100

	return rounded(amount), currency


def get_current_exchange_rate(source: str, target: str = "USD") -> float:
	url = f"https://api.frankfurter.app/latest?from={source}&to={target}"

	response = requests.request("GET", url)
	details = response.json()
	return details["rates"][target]


def guest_access_allowed():
	allow_guest_access = frappe.get_cached_value("LMS Settings", None, "allow_guest_access")
	if frappe.session.user == "Guest" and not allow_guest_access:
		return False
	return True


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=500, seconds=60 * 60)
def get_courses(filters: dict = None, start: int = 0) -> list:
	"""Returns the list of courses."""

	if not guest_access_allowed():
		return []

	if not filters:
		filters = {}

	filters, or_filters, show_featured = update_course_filters(filters)
	fields = get_course_fields()

	courses = frappe.get_all(
		"LMS Course",
		filters=filters,
		fields=fields,
		or_filters=or_filters,
		order_by="enrollments desc",
		start=start,
		page_length=30,
	)
	if show_featured and start == 0:
		courses = get_featured_courses(filters, or_filters, fields) + courses

	courses = get_enrollment_details(courses)
	courses = get_course_card_details(courses)
	return courses


def get_course_card_details(courses: list) -> list:
	for course in courses:
		course.instructors = get_instructors("LMS Course", course.name)

		if course.paid_course and course.published == 1:
			course.amount, course.currency = check_multicurrency(
				course.course_price, course.currency, None, course.amount_usd
			)
			course.price = fmt_money(course.amount, 0, course.currency)

	return courses


def get_course_or_filters(filters: dict) -> dict:
	or_filters = {}
	or_filters.update({"title": filters.get("title")})
	or_filters.update({"short_introduction": filters.get("title")})
	or_filters.update({"description": filters.get("title")})
	or_filters.update({"tags": filters.get("title")})
	return or_filters


def update_course_filters(filters: dict) -> tuple:
	or_filters = {}
	show_featured = False

	if filters.get("title"):
		or_filters = get_course_or_filters(filters)
		del filters["title"]

	if filters.get("enrolled"):
		enrolled_courses = frappe.get_all("LMS Enrollment", {"member": frappe.session.user}, pluck="course")
		filters.update({"name": ["in", enrolled_courses]})
		del filters["enrolled"]

	if filters.get("created"):
		created_courses = frappe.get_all(
			"Course Instructor", {"instructor": frappe.session.user}, pluck="parent"
		)
		filters.update({"name": ["in", created_courses]})
		del filters["created"]

	if filters.get("live"):
		filters.update({"featured": 0})
		show_featured = True
		del filters["live"]

	if filters.get("certification"):
		or_filters.update({"enable_certification": 1})
		del filters["certification"]

	# Exclude resources from the course catalog
	filters["course_type"] = ["!=", "Resource"]

	return filters, or_filters, show_featured


def get_enrollment_details(courses: list) -> list:
	for course in courses:
		filters = {
			"course": course.name,
			"member": frappe.session.user,
		}

		if frappe.db.exists("LMS Enrollment", filters):
			course.membership = frappe.db.get_value(
				"LMS Enrollment",
				filters,
				["name", "course", "current_lesson", "progress", "member"],
				as_dict=1,
			)

	return courses


def get_featured_courses(filters: dict, or_filters: dict, fields: list) -> list:
	filters.update({"featured": 1})
	featured_courses = frappe.get_all(
		"LMS Course",
		filters=filters,
		fields=fields,
		or_filters=or_filters,
		order_by="enrollments desc",
	)
	return featured_courses


def get_course_fields():
	return [
		"name",
		"title",
		"tags",
		"image",
		"video_link",
		"card_gradient",
		"short_introduction",
		"description",
		"published",
		"upcoming",
		"featured",
		"disable_self_learning",
		"published_on",
		"category",
		"status",
		"paid_course",
		"course_price",
		"currency",
		"amount_usd",
		"enable_certification",
		"lessons",
		"enrollments",
		"rating",
		"ceu_hours",
		"course_type",
		"resource_type",
		"route",
	]


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=500, seconds=60 * 60)
def get_course_details(course: str):
	if not guest_access_allowed():
		return {}

	is_course_published = frappe.db.get_value("LMS Course", course, "published")
	membership = get_membership(course)
	if not is_course_published and not can_modify_course(course) and not membership:
		return {}

	fields = get_course_fields()
	course_details = frappe.db.get_value(
		"LMS Course",
		course,
		fields,
		as_dict=1,
	)

	course_details.instructors = get_instructors("LMS Course", course_details.name)
	course_details.membership = membership
	# course_details.is_instructor = is_instructor(course_details.name)
	if course_details.paid_course:
		course_details.price = fmt_money(course_details.course_price, 0, course_details.currency)

	if frappe.session.user == "Guest":
		course_details.is_instructor = False

	if course_details.membership and course_details.membership.current_lesson:
		course_details.current_lesson = get_lesson_index(course_details.membership.current_lesson)

	return course_details


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=500, seconds=60 * 60)
def get_resources(filters: dict = None, start: int = 0) -> list:
	"""Returns the list of published resources (courses with course_type='Resource')."""
	if not filters:
		filters = {}

	or_filters = {}

	# Always filter to resources only
	filters["course_type"] = "Resource"
	filters["published"] = 1

	# Handle resource_type filter
	if filters.get("resource_type"):
		pass  # Already in filters dict, will be applied directly
	else:
		filters.pop("resource_type", None)

	# Restrict to resources the current user has claimed/enrolled in.
	only_enrolled = filters.pop("only_enrolled", None)
	if only_enrolled:
		if frappe.session.user == "Guest":
			return []
		enrolled = frappe.get_all(
			"LMS Enrollment",
			filters={"member": frappe.session.user},
			pluck="course",
		)
		if not enrolled:
			return []
		filters["name"] = ["in", enrolled]

	# Handle text search
	if filters.get("title"):
		or_filters["title"] = filters["title"]
		or_filters["short_introduction"] = filters["title"]
		or_filters["description"] = filters["title"]
		or_filters["tags"] = filters["title"]
		del filters["title"]

	fields = get_course_fields()

	resources = frappe.get_all(
		"LMS Course",
		filters=filters,
		fields=fields,
		or_filters=or_filters,
		order_by="creation desc",
		start=start,
		page_length=30,
	)

	resources = get_enrollment_details(resources)
	resources = get_course_card_details(resources)
	return resources


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=500, seconds=60 * 60)
def get_resource_details(resource: str):
	"""Returns resource details including single-lesson detection."""
	course_details = get_course_details(resource)
	if not course_details:
		return {}

	# Check if this is a single-lesson resource
	chapters = frappe.get_all(
		"Course Chapter",
		filters={"course": resource},
		fields=["name", "title"],
		order_by="idx",
	)

	is_single_lesson = False
	single_lesson = None

	if len(chapters) == 1:
		lessons = frappe.get_all(
			"Course Lesson",
			filters={"chapter": chapters[0].name},
			fields=["name", "title", "body", "youtube", "quiz_id", "content"],
			order_by="idx",
		)
		if len(lessons) == 1:
			is_single_lesson = True
			single_lesson = lessons[0]

	course_details.is_single_lesson = is_single_lesson
	course_details.single_lesson = single_lesson
	return course_details


def get_categorized_courses(courses: list) -> dict:
	live, upcoming, new, enrolled, created, under_review = [], [], [], [], [], []

	for course in courses:
		if course.status == "Under Review":
			under_review.append(course)
		elif course.published and course.upcoming:
			upcoming.append(course)
		elif course.published:
			live.append(course)

		if course.published and not course.upcoming and course.published_on > add_months(getdate(), -3):
			new.append(course)

		if course.membership:
			enrolled.append(course)
		elif course.is_instructor:
			created.append(course)

		categories = [live, enrolled, created]
		for category in categories:
			category.sort(key=lambda x: cint(x.enrollments), reverse=True)

		live.sort(key=lambda x: x.featured, reverse=True)

	return {
		"live": live,
		"new": new,
		"upcoming": upcoming,
		"enrolled": enrolled,
		"created": created,
		"under_review": under_review,
	}


@frappe.whitelist(allow_guest=True)
def get_course_outline(course: str, progress: bool = False) -> list:
	"""Returns the course outline."""

	if not guest_access_allowed():
		return []

	outline = []
	chapters = frappe.get_all("Chapter Reference", {"parent": course}, ["chapter", "idx"], order_by="idx")
	for chapter in chapters:
		chapter_details = frappe.db.get_value(
			"Course Chapter",
			chapter.chapter,
			["name", "title", "is_scorm_package", "launch_file", "scorm_package"],
			as_dict=True,
		)
		chapter_details["idx"] = chapter.idx
		chapter_details.lessons = get_lessons(course, chapter_details, progress=progress)

		if chapter_details.is_scorm_package:
			chapter_details.scorm_package = frappe.db.get_value(
				"File",
				chapter_details.scorm_package,
				["file_name", "file_size", "file_url"],
				as_dict=1,
			)

		outline.append(chapter_details)
	return outline


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=500, seconds=60 * 60)
def get_lesson(course: str, chapter: int, lesson: int) -> dict:
	if not guest_access_allowed():
		return {}

	chapter_name = frappe.db.get_value("Chapter Reference", {"parent": course, "idx": chapter}, "chapter")
	lesson_name = frappe.db.get_value("Lesson Reference", {"parent": chapter_name, "idx": lesson}, "lesson")
	lesson_details = frappe.db.get_value(
		"Course Lesson",
		lesson_name,
		["include_in_preview", "title", "is_scorm_package"],
		as_dict=1,
	)

	if not lesson_details:
		return {}

	if lesson_details.is_scorm_package:
		return {
			"is_scorm_package": True,
			"chapter_name": chapter_name,
		}

	membership = get_membership(course)
	course_info = frappe.db.get_value(
		"LMS Course",
		course,
		["title", "disable_self_learning", "enable_certification"],
		as_dict=1,
	)

	if not lesson_details.include_in_preview and not membership and not can_modify_course(course):
		return {
			"no_preview": 1,
			"title": lesson_details.title,
			"course_title": course_info.title,
			"disable_self_learning": course_info.disable_self_learning,
		}

	lesson_details = frappe.db.get_value(
		"Course Lesson",
		lesson_name,
		[
			"name",
			"title",
			"include_in_preview",
			"body",
			"creation",
			"youtube",
			"quiz_id",
			"question",
			"file_type",
			"instructor_notes",
			"course",
			"content",
			"instructor_content",
		],
		as_dict=True,
	)

	if frappe.session.user == "Guest":
		progress = 0
	else:
		progress = get_progress(course, lesson_details.name)

	lesson_details.chapter_title = frappe.db.get_value("Course Chapter", chapter_name, "title")
	neighbours = get_neighbour_lesson(course, chapter, lesson)
	lesson_details.next = neighbours["next"]
	lesson_details.progress = progress
	lesson_details.prev = neighbours["prev"]
	lesson_details.membership = membership
	lesson_details.icon = get_lesson_icon(lesson_details.body, lesson_details.content)
	lesson_details.instructors = get_instructors("LMS Course", course)
	lesson_details.course_title = course_info.title
	lesson_details.disable_self_learning = course_info.disable_self_learning
	lesson_details.enable_certification = course_info.enable_certification
	lesson_details.videos = get_video_details(lesson_name)
	return lesson_details


def get_video_details(lesson_name: str) -> list:
	return frappe.get_all(
		"LMS Video Watch Duration",
		{"lesson": lesson_name, "member": frappe.session.user},
		["source", "watch_time"],
	)


def get_neighbour_lesson(course: str, chapter: int, lesson: int) -> dict:
	numbers = []
	current = f"{chapter}.{lesson}"
	chapters = frappe.get_all("Chapter Reference", {"parent": course}, ["idx", "chapter"])
	for chapter in chapters:
		lessons = frappe.get_all("Lesson Reference", {"parent": chapter.chapter}, pluck="idx")
		for lesson in lessons:
			numbers.append(f"{chapter.idx}.{lesson}")

	tuples_list = [tuple(int(x) for x in s.split(".")) for s in numbers]
	sorted_tuples = sorted(tuples_list)
	sorted_numbers = [".".join(str(num) for num in t) for t in sorted_tuples]
	index = sorted_numbers.index(current)

	return {
		"prev": sorted_numbers[index - 1] if index - 1 >= 0 else None,
		"next": sorted_numbers[index + 1] if index + 1 < len(sorted_numbers) else None,
	}


WEBINAR_WINDOW_LEAD_MINUTES = 15


def is_webinar_window_open(event: str) -> bool:
	"""True when server time is within (start - 15 min) through end_time of any event_day.
	Times are compared naively in server-local time, matching how `accept_enrollments`
	is computed elsewhere — accurate enough for the manual-link UX, where the email
	is the primary delivery and the in-app button is a backup."""
	days = frappe.get_all(
		"LMS Event Day",
		filters={"parent": event, "parenttype": "LMS Event"},
		fields=["date", "start_time", "end_time"],
	)
	if not days:
		start_date, start_time, end_time = frappe.db.get_value(
			"LMS Event", event, ["start_date", "start_time", "end_time"]
		)
		if not (start_date and start_time and end_time):
			return False
		days = [{"date": start_date, "start_time": start_time, "end_time": end_time}]

	now = now_datetime()
	for day in days:
		try:
			start_dt = get_datetime(f"{day['date']} {day['start_time']}")
			end_dt = get_datetime(f"{day['date']} {day['end_time']}")
		except Exception:
			continue
		if start_dt - timedelta(minutes=WEBINAR_WINDOW_LEAD_MINUTES) <= now <= end_dt:
			return True
	return False


@frappe.whitelist(allow_guest=True)  # nosemgrep: frappe-semgrep-rules.rules.security.guest-whitelisted-method
@rate_limit(limit=500, seconds=60 * 60)
def get_event_details(batch: str):
	if not guest_access_allowed():
		return {}

	batch_students = frappe.get_all("LMS Event Registration", {"event": batch}, pluck="member")
	is_batch_admin = can_modify_event(batch)
	is_batch_published = frappe.db.get_value("LMS Event", batch, "published")
	is_student_enrolled = frappe.session.user in batch_students

	if not (is_batch_published or is_batch_admin or is_student_enrolled):
		return {}

	event_details = frappe.db.get_value(
		"LMS Event",
		batch,
		[
			"name",
			"title",
			"description",
			"event_details",
			"event_details_raw",
			"start_date",
			"end_date",
			"start_time",
			"end_time",
			"seat_count",
			"published",
			"amount",
			"amount_usd",
			"currency",
			"paid_event",
			"early_bird_amount",
			"early_bird_amount_usd",
			"early_bird_deadline",
			"evaluation_end_date",
			"allow_self_enrollment",
			"certification",
			"evaluation",
			"timezone",
			"zoom_account",
			"conferencing_provider",
			"google_meet_account",
			"zoom_link",
			"video_link",
			"event_type",
			"venue",
			"credit_hours",
			"survey_quiz",
			"route",
		],
		as_dict=True,
	)

	if not (is_batch_admin or is_student_enrolled):
		event_details.zoom_link = None

	event_details.webinar_window_open = is_webinar_window_open(batch)

	event_details.categories = frappe.get_all(
		"LMS Event Category",
		filters={"parent": batch, "parenttype": "LMS Event"},
		pluck="category",
		order_by="idx",
	)
	event_details.event_days = frappe.get_all(
		"LMS Event Day",
		filters={"parent": batch, "parenttype": "LMS Event"},
		fields=["date", "start_time", "end_time"],
		order_by="idx",
	)

	event_details.instructors = get_instructors("LMS Event", batch)
	event_details.accept_enrollments = event_details.start_date > getdate()

	if (
		not event_details.accept_enrollments
		and event_details.start_date == getdate()
		and str(event_details.start_time) > nowtime()
	):
		event_details.accept_enrollments = True

	event_details.courses = frappe.get_all(
		"Batch Course", filters={"parent": batch}, fields=["course", "title", "evaluator"]
	)
	event_details.assessments = frappe.get_all(
		"LMS Assessment", {"parent": batch}, ["assessment_name", "assessment_type"]
	)

	if can_modify_event(batch):
		event_details.students = batch_students
	elif is_student_enrolled:
		event_details.students = [frappe.session.user]

	if event_details.paid_event and event_details.start_date >= getdate():
		event_details.amount, event_details.currency = check_multicurrency(
			event_details.amount, event_details.currency, None, event_details.amount_usd
		)
		event_details.price = fmt_money(event_details.amount, 0, event_details.currency)

	if event_details.seat_count:
		event_details.seats_left = event_details.seat_count - len(batch_students)

	event_details.survey_open = compute_event_survey_open(event_details)
	event_details.survey_submitted = bool(
		is_student_enrolled
		and event_details.survey_quiz
		and frappe.db.exists(
			"LMS Quiz Submission",
			{
				"event_name": batch,
				"member": frappe.session.user,
				"quiz": event_details.survey_quiz,
			},
		)
	)

	return event_details


SURVEY_OPEN_OFFSET_MINUTES = 30


def compute_event_survey_open(event_details):
	"""Return True when the post-event survey window has opened.

	Window opens `SURVEY_OPEN_OFFSET_MINUTES` before the final scheduled
	`event_day.end_time` (falling back to top-level `end_date` + `end_time`
	for events that pre-date the event_days child table). The offset gives
	presenters room to show the QR code before they actually wrap, since
	they often end a few minutes early. Requires certification + a configured
	survey_quiz.
	"""
	if not event_details.get("certification") or not event_details.get("survey_quiz"):
		return False
	days = event_details.get("event_days") or []
	if days:
		last_day = days[-1]
		date_str = last_day.get("date")
		time_str = last_day.get("end_time")
	else:
		date_str = event_details.get("end_date")
		time_str = event_details.get("end_time")
	if not date_str or not time_str:
		return False
	end_dt = get_datetime(f"{date_str} {time_str}")
	return now_datetime() >= end_dt - timedelta(minutes=SURVEY_OPEN_OFFSET_MINUTES)


def categorize_batches(batches: list) -> dict:
	upcoming, archived, private, enrolled = [], [], [], []

	for batch in batches:
		if not batch.published:
			private.append(batch)
		elif getdate(batch.start_date) < getdate():
			archived.append(batch)
		elif getdate(batch.start_date) == getdate() and str(batch.start_time) < nowtime():
			archived.append(batch)
		else:
			upcoming.append(batch)

		if frappe.session.user != "Guest":
			if frappe.db.exists("LMS Event Registration", {"member": frappe.session.user, "event": batch.name}):
				enrolled.append(batch)

	categories = [archived, private, enrolled]
	for category in categories:
		category.sort(key=lambda x: x.start_date, reverse=True)

	upcoming.sort(key=lambda x: x.start_date)
	return {
		"upcoming": upcoming,
		"archived": archived,
		"private": private,
		"enrolled": enrolled,
	}


def get_country_code():
	ip = frappe.local.request_ip
	res = requests.get(f"http://ip-api.com/json/{ip}")

	try:
		data = res.json()
		if data.get("status") != "fail":
			return frappe.db.get_value("Country", {"code": data.get("countryCode")}, "name")
	except Exception:
		pass
	return


@frappe.whitelist()
def get_question_details(question: str) -> dict:
	if not has_lms_role():
		frappe.throw(_("You are not authorized to view the question details."))

	fields = ["question", "type", "multiple"]
	for i in range(1, 5):
		fields.append(f"option_{i}")
		fields.append(f"explanation_{i}")

	question_details = frappe.db.get_value("LMS Question", question, fields, as_dict=1)
	return question_details


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=500, seconds=60 * 60)
def get_batch_courses(batch: str) -> list:
	if not guest_access_allowed():
		return []

	courses = []
	course_list = frappe.get_all("Batch Course", {"parent": batch}, ["name", "course"])

	for course in course_list:
		details = get_course_details(course.course)
		if details.get("name"):
			details.batch_course = course.name
			courses.append(details)

	return courses


# Alias for frontend compatibility (Batch→Event rename)
get_event_courses = get_batch_courses


@frappe.whitelist()
def get_assessments(batch: str) -> list:
	member = frappe.session.user
	is_enrolled = frappe.db.exists("LMS Event Registration", {"event": batch, "member": member})
	if not is_enrolled and not can_modify_event(batch):
		frappe.throw(_("You are not authorized to view the assessments of this event."))

	assessments = frappe.get_all(
		"LMS Assessment",
		{"parent": batch},
		["name", "assessment_type", "assessment_name"],
		order_by="idx",
	)

	for assessment in assessments:
		if assessment.assessment_type == "LMS Assignment":
			assessment = get_assignment_details(assessment, member)

		elif assessment.assessment_type == "LMS Quiz":
			assessment = get_quiz_details(assessment, member)

		elif assessment.assessment_type == "LMS Programming Exercise":
			assessment = get_exercise_details(assessment, member)

	return assessments


def get_assignment_details(assessment: dict, member: str) -> dict:
	assessment.title = frappe.db.get_value("LMS Assignment", assessment.assessment_name, "title")

	existing_submission = frappe.db.exists(
		{
			"doctype": "LMS Assignment Submission",
			"member": member,
			"assignment": assessment.assessment_name,
		}
	)
	assessment.completed = False
	if existing_submission:
		assessment.submission = frappe.db.get_value(
			"LMS Assignment Submission",
			existing_submission,
			["name", "status", "comments"],
			as_dict=True,
		)
		assessment.completed = True
		assessment.status = assessment.submission.status
	else:
		assessment.status = "Not Attempted"
		assessment.color = "red"

	assessment.edit_url = f"/assignments/{assessment.assessment_name}"
	submission_name = existing_submission if existing_submission else "new-submission"
	assessment.url = get_lms_route(f"assignment-submission/{assessment.assessment_name}/{submission_name}")

	return assessment


def get_quiz_details(assessment: dict, member: str) -> dict:
	assessment_details = frappe.db.get_value(
		"LMS Quiz", assessment.assessment_name, ["title", "passing_percentage"], as_dict=1
	)
	assessment.title = assessment_details.title

	existing_submission = frappe.get_all(
		"LMS Quiz Submission",
		{
			"member": member,
			"quiz": assessment.assessment_name,
		},
		["name", "score", "percentage"],
		order_by="percentage desc",
	)

	if len(existing_submission):
		assessment.submission = existing_submission[0]
		assessment.completed = True
		assessment.status = assessment.submission.percentage or assessment.submission.score
	else:
		assessment.status = "Not Attempted"
		assessment.color = "red"
		assessment.completed = False

	assessment.edit_url = f"/quizzes/{assessment.assessment_name}"
	submission_name = existing_submission[0].name if len(existing_submission) else "new-submission"
	assessment.url = f"/quiz-submission/{assessment.assessment_name}/{submission_name}"

	return assessment


def get_exercise_details(assessment: dict, member: str) -> dict:
	assessment.title = frappe.db.get_value("LMS Programming Exercise", assessment.assessment_name, "title")
	filters = {"member": member, "exercise": assessment.assessment_name}

	if frappe.db.exists("LMS Programming Exercise Submission", filters):
		assessment.submission = frappe.db.get_value(
			"LMS Programming Exercise Submission",
			filters,
			["name", "status"],
			as_dict=True,
		)
		assessment.completed = True
		assessment.status = assessment.submission.status
		assessment.edit_url = (
			f"/exercises/{assessment.assessment_name}/submission/{assessment.submission.name}"
		)
	else:
		assessment.status = "Not Attempted"
		assessment.color = "red"
		assessment.completed = False
		assessment.edit_url = f"/exercises/{assessment.assessment_name}/submission/new"


@frappe.whitelist()
def get_batch_student_progress(member: str, batch: str) -> dict:
	if not can_modify_event(batch):
		frappe.throw(_("You are not authorized to view the students of this event."))

	details = get_batch_student_details(member)
	calculate_student_progress(batch, details)
	return details


def get_course_completion_stats(batch: str) -> list:
	"""Get completion counts per course in batch"""
	BatchCourse = frappe.qb.DocType("Batch Course")
	BatchEnrollment = frappe.qb.DocType("LMS Event Registration")
	Enrollment = frappe.qb.DocType("LMS Enrollment")

	rows = (
		frappe.qb.from_(BatchCourse)
		.left_join(BatchEnrollment)
		.on(BatchEnrollment.event == BatchCourse.parent)
		.left_join(Enrollment)
		.on((Enrollment.course == BatchCourse.course) & (Enrollment.member == BatchEnrollment.member))
		.where(BatchCourse.parent == batch)
		.groupby(BatchCourse.course, BatchCourse.title)
		.select(
			BatchCourse.title,
			fn.Count(Case().when(Enrollment.progress == 100, Enrollment.member)).distinct().as_("completed"),
		)
	).run(as_dict=True)

	return [{"task": row.title, "value": row.completed or 0} for row in rows]


def get_assignment_pass_stats(batch: str) -> list:
	"""Get pass counts per assignment in batch"""
	Assessment = frappe.qb.DocType("LMS Assessment")
	Assignment = frappe.qb.DocType("LMS Assignment")
	BatchEnrollment = frappe.qb.DocType("LMS Event Registration")
	Submission = frappe.qb.DocType("LMS Assignment Submission")

	rows = (
		frappe.qb.from_(Assessment)
		.join(Assignment)
		.on(Assignment.name == Assessment.assessment_name)
		.left_join(BatchEnrollment)
		.on(BatchEnrollment.event == Assessment.parent)
		.left_join(Submission)
		.on(
			(Submission.assignment == Assessment.assessment_name)
			& (Submission.member == BatchEnrollment.member)
		)
		.where((Assessment.parent == batch) & (Assessment.assessment_type == "LMS Assignment"))
		.groupby(Assessment.assessment_name, Assignment.title)
		.select(
			Assignment.title,
			fn.Count(Case().when(Submission.status == "Pass", Submission.member)).distinct().as_("passed"),
		)
	).run(as_dict=True)

	return [{"task": row.title, "value": row.passed or 0} for row in rows]


def get_quiz_pass_stats(batch: str) -> list:
	"""Get pass counts per quiz in batch"""
	Assessment = frappe.qb.DocType("LMS Assessment")
	Quiz = frappe.qb.DocType("LMS Quiz")
	BatchEnrollment = frappe.qb.DocType("LMS Event Registration")
	Submission = frappe.qb.DocType("LMS Quiz Submission")

	rows = (
		frappe.qb.from_(Assessment)
		.join(Quiz)
		.on(Quiz.name == Assessment.assessment_name)
		.left_join(BatchEnrollment)
		.on(BatchEnrollment.event == Assessment.parent)
		.left_join(Submission)
		.on((Submission.quiz == Assessment.assessment_name) & (Submission.member == BatchEnrollment.member))
		.where((Assessment.parent == batch) & (Assessment.assessment_type == "LMS Quiz"))
		.groupby(Assessment.assessment_name, Quiz.title)
		.select(
			Quiz.title,
			fn.Count(Case().when(Submission.percentage >= Submission.passing_percentage, Submission.member))
			.distinct()
			.as_("passed"),
		)
	).run(as_dict=True)

	return [{"task": row.title, "value": row.passed or 0} for row in rows]


@frappe.whitelist()
def get_event_chart_data(batch: str) -> list:
	"""Get completion counts per course and assessment"""
	if not can_modify_event(batch):
		frappe.throw(_("You are not authorized to view the chart data of this event."))
	if not frappe.db.exists("LMS Event", batch):
		frappe.throw(_("The specified event does not exist."))

	return get_course_completion_stats(batch) + get_assignment_pass_stats(batch) + get_quiz_pass_stats(batch)


def get_batch_student_details(student: str) -> dict:
	details = frappe.db.get_value(
		"User",
		student,
		["full_name", "email", "username", "last_active", "user_image", "name"],
		as_dict=True,
	)
	details.last_active = format_datetime(details.last_active, "dd MMM YY")
	return details


def calculate_student_progress(batch: str, details: dict):
	batch_courses = frappe.get_all("Batch Course", {"parent": batch}, ["course", "title"])
	assessments = frappe.get_all(
		"LMS Assessment",
		filters={"parent": batch},
		fields=["name", "assessment_type", "assessment_name"],
	)

	calculate_course_progress(batch_courses, details)
	calculate_assessment_progress(assessments, details)

	if len(batch_courses) + len(assessments):
		details.progress = flt(
			(
				(details.average_course_progress * len(batch_courses))
				+ (details.average_assessments_progress * len(assessments))
			)
			/ (len(batch_courses) + len(assessments)),
			2,
		)
	else:
		details.progress = 0


def calculate_course_progress(batch_courses: list, details: dict):
	course_progress = []
	details.courses = []
	for course in batch_courses:
		progress = (
			frappe.db.get_value(
				"LMS Enrollment", {"course": course.course, "member": details.email}, "progress"
			)
			or 0
		)
		details.courses.append({"course": course.course, "title": course.title, "progress": progress})
		course_progress.append(progress)

	details.average_course_progress = (
		flt(sum(course_progress) / len(batch_courses), 2) if len(batch_courses) else 0
	)


def calculate_assessment_progress(assessments: list, details: dict):
	assessments_completed = 0
	details.assessments = []

	for assessment in assessments:
		title = frappe.db.get_value(assessment.assessment_type, assessment.assessment_name, "title")
		assessment_info = has_submitted_assessment(
			assessment.assessment_name, assessment.assessment_type, details.email
		)
		assessment_info.title = title
		details.assessments.append(assessment_info)

		if assessment_info.result == "Pass":
			assessments_completed += 1

	details.average_assessments_progress = (
		flt((assessments_completed / len(assessments) * 100), 2) if len(assessments) else 0
	)


def has_submitted_assessment(assessment: str, assessment_type: str, member: str = None):
	if not member:
		member = frappe.session.user

	doctype, docfield, fields, not_attempted = get_assessment_meta(assessment_type)
	filters = {}
	filters[docfield] = assessment
	filters["member"] = member

	attempt = frappe.db.exists(doctype, filters)
	if attempt:
		return get_assessment_attempt_details(doctype, filters, fields, assessment_type, assessment)
	else:
		return frappe._dict(
			{
				"status": not_attempted,
				"result": "Failed",
			}
		)


def get_assessment_meta(assessment_type: str):
	if assessment_type == "LMS Assignment":
		doctype = "LMS Assignment Submission"
		docfield = "assignment"
		fields = ["status"]
		not_attempted = "Not Attempted"
	elif assessment_type == "LMS Quiz":
		doctype = "LMS Quiz Submission"
		docfield = "quiz"
		fields = ["percentage"]
		not_attempted = 0
	elif assessment_type == "LMS Programming Exercise":
		doctype = "LMS Programming Exercise Submission"
		docfield = "exercise"
		fields = ["status"]
		not_attempted = "Not Attempted"

	return doctype, docfield, fields, not_attempted


def get_assessment_attempt_details(
	doctype: str, filters: dict, fields: list, assessment_type: str, assessment: str
):
	fields.append("name")
	attempt_details = frappe.db.get_value(doctype, filters, fields, as_dict=1)
	if assessment_type == "LMS Quiz":
		result = "Failed"
		passing_percentage = frappe.db.get_value("LMS Quiz", assessment, "passing_percentage")
		if attempt_details.percentage >= passing_percentage:
			result = "Pass"
	else:
		result = attempt_details.status
	return frappe._dict(
		{
			"status": attempt_details.percentage if assessment_type == "LMS Quiz" else attempt_details.status,
			"result": result,
			"assessment": assessment,
			"type": assessment_type,
			"submission": attempt_details.name,
		}
	)


def can_access_topic(doctype: str, docname: str) -> bool:
	is_student = False
	if doctype == "Course Lesson":
		course = frappe.db.get_value("Course Lesson", docname, "course")
		is_student = frappe.db.exists("LMS Enrollment", {"course": course, "member": frappe.session.user})
		if not is_student and not can_modify_course(course):
			return False
	elif doctype == "LMS Event":
		is_student = frappe.db.exists(
			"LMS Event Registration", {"event": docname, "member": frappe.session.user}
		)
		if not is_student and not can_modify_event(docname):
			return False
	return True


@frappe.whitelist()
def get_discussion_topics(doctype: str, docname: str, single_thread: bool = False):
	if not can_access_topic(doctype, docname):
		frappe.throw(_("You are not authorized to view the discussion topics for this item."))

	if single_thread:
		filters = {
			"reference_doctype": doctype,
			"reference_docname": docname,
		}
		topic = frappe.db.exists("Discussion Topic", filters)
		if topic:
			return frappe.db.get_value("Discussion Topic", topic, ["name"], as_dict=1)
		else:
			return create_discussion_topic(doctype, docname)
	topics = frappe.get_all(
		"Discussion Topic",
		{
			"reference_doctype": doctype,
			"reference_docname": docname,
		},
		["name", "title", "owner", "creation", "modified"],
		order_by="creation desc",
	)

	for topic in topics:
		topic.user = frappe.db.get_value("User", topic.owner, ["full_name", "user_image"], as_dict=True)

	return topics


def create_discussion_topic(doctype: str, docname: str) -> str:
	doc = frappe.new_doc("Discussion Topic")
	doc.update(
		{
			"title": docname,
			"reference_doctype": doctype,
			"reference_docname": docname,
		}
	)
	doc.insert()
	return doc


@frappe.whitelist()
def get_discussion_replies(topic: str):
	topic_details = frappe.db.get_value(
		"Discussion Topic", topic, ["reference_doctype", "reference_docname"], as_dict=True
	)
	if not can_access_topic(topic_details.reference_doctype, topic_details.reference_docname):
		frappe.throw(_("You are not authorized to view the discussion replies for this topic."))

	replies = frappe.get_all(
		"Discussion Reply",
		{
			"topic": topic,
		},
		["name", "owner", "creation", "modified", "reply"],
		order_by="creation",
	)

	for reply in replies:
		reply.user = frappe.db.get_value("User", reply.owner, ["full_name", "user_image"], as_dict=True)

	return replies


@frappe.whitelist()
def get_lesson_creation_details(course: str, chapter: int, lesson: int) -> dict:
	frappe.only_for(["Moderator"])
	chapter_name = frappe.db.get_value("Chapter Reference", {"parent": course, "idx": chapter}, "chapter")
	lesson_name = frappe.db.get_value("Lesson Reference", {"parent": chapter_name, "idx": lesson}, "lesson")

	if lesson_name:
		lesson_details = frappe.db.get_value(
			"Course Lesson",
			lesson_name,
			[
				"name",
				"title",
				"include_in_preview",
				"body",
				"content",
				"instructor_notes",
				"instructor_content",
				"youtube",
				"quiz_id",
			],
			as_dict=1,
		)

	return {
		"course_title": frappe.db.get_value("LMS Course", course, "title"),
		"chapter": frappe.db.get_value("Course Chapter", chapter_name, ["title", "name"], as_dict=True),
		"lesson": lesson_details if lesson_name else None,
	}


@frappe.whitelist()
def get_roles(name: str) -> dict:
	frappe.only_for(["Moderator"])
	return {
		"moderator": has_moderator_role(name),
		"lms_student": has_student_role(name),
	}


def publish_notifications(doc: Document, method: str):
	frappe.publish_realtime("publish_lms_notifications", user=doc.for_user, after_commit=True)


def get_audience_recipients(audience: str | None, extra_users: list = None) -> list:
	"""Return the list of enabled user emails to receive a new-content
	notification for content targeted at ``audience``.

	When ``audience`` is falsy, every enabled user is returned (preserves the
	pre-targeting fan-out behavior). When set, the result is restricted to users
	whose ``notification_audience`` matches the given audience OR is unset
	(catch-all default — users who haven't expressed a preference still receive
	the notification). ``extra_users`` (e.g. course/event instructors) are always
	included regardless of preference so the people responsible for the content
	don't accidentally filter themselves out.
	"""
	extras = [u for u in (extra_users or []) if u]
	if not audience:
		return frappe.get_all("User", {"enabled": 1}, pluck="name")

	from frappe.query_builder import DocType

	User = DocType("User")
	rows = (
		frappe.qb.from_(User)
		.select(User.name)
		.where(User.enabled == 1)
		.where(
			(User.notification_audience == audience)
			| (User.notification_audience.isnull())
			| (User.notification_audience == "")
		)
		.run(pluck=True)
	)
	if extras:
		merged = list(dict.fromkeys(list(rows) + extras))
		return merged
	return list(rows)


@frappe.whitelist()
def get_programs():
	if not guest_access_allowed():
		frappe.throw(_("Please login to view programs."))

	enrolled_programs = frappe.get_all(
		"LMS Program Member", {"member": frappe.session.user}, ["parent as name", "progress"]
	)
	for program in enrolled_programs:
		program.update(
			frappe.db.get_value(
				"LMS Program", program.name, ["name", "course_count", "member_count"], as_dict=True
			)
		)

	published_programs = frappe.get_all(
		"LMS Program",
		{
			"published": 1,
		},
		["name", "course_count", "member_count"],
	)

	programs_to_remove = []
	for program in published_programs:
		if program.name in [p.name for p in enrolled_programs]:
			programs_to_remove.append(program)
	published_programs = [program for program in published_programs if program not in programs_to_remove]

	return {
		"enrolled": enrolled_programs,
		"published": published_programs,
	}


@frappe.whitelist()
def get_program_details(program_name: str) -> dict:
	if not guest_access_allowed():
		frappe.throw(_("Please login to view program details."))

	is_published = frappe.db.get_value("LMS Program", program_name, "published")
	is_member = frappe.db.exists(
		"LMS Program Member", {"parent": program_name, "member": frappe.session.user}
	)
	if not is_published and not is_member:
		frappe.throw(_("You are not authorized to view the details of this program."))

	program = frappe.db.get_value(
		"LMS Program",
		program_name,
		[
			"name",
			"member_count",
			"course_count",
			"published",
			"enforce_course_order",
		],
		as_dict=1,
	)
	program_courses = frappe.get_all(
		"LMS Program Course", {"parent": program_name}, ["course"], order_by="idx"
	)

	program.courses = []
	previous_progress = 0
	for i, course in enumerate(program_courses):
		details = get_course_details(course.course)
		if i == 0:
			details.eligible = True
		elif previous_progress == 100:
			details.eligible = True
		else:
			details.eligible = False

		previous_progress = details.membership.progress if details.membership else 0
		program.courses.append(details)
		if frappe.session.user != "Guest":
			program.progress = frappe.db.get_value(
				"LMS Program Member",
				{"parent": program_name, "member": frappe.session.user},
				"progress",
			)

	return program


@frappe.whitelist()
def enroll_in_program(program: str):
	validate_program_enrollment(program)

	if not frappe.db.exists("LMS Program Member", {"parent": program, "member": frappe.session.user}):
		program_member = frappe.new_doc("LMS Program Member")
		program_member.update(
			{
				"parent": program,
				"parenttype": "LMS Program",
				"parentfield": "members",
				"member": frappe.session.user,
			}
		)
		program_member.save(ignore_permissions=True)


def validate_program_enrollment(program: str):
	published = frappe.db.get_value("LMS Program", program, "published")
	if not published:
		frappe.throw(_("You cannot enroll in an unpublished program."))


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=500, seconds=60 * 60)
def get_batches(filters: dict = None, start: int = 0, order_by: str = "start_date"):
	if not guest_access_allowed():
		return []

	if not filters:
		filters = {}

	if filters.get("enrolled"):
		enrolled_batches = frappe.get_all(
			"LMS Event Registration", {"member": frappe.session.user}, pluck="event"
		)
		filters.update({"name": ["in", enrolled_batches]})
		del filters["enrolled"]

	# `category` is a child-table multiselect — translate the filter into a
	# `name in (parents of LMS Event Category rows where category = X)` lookup.
	# Single-select dropdown still drives this; "any of the event's categories
	# matches" is the desired semantic.
	if filters.get("category"):
		matching_events = frappe.get_all(
			"LMS Event Category",
			filters={"category": filters["category"], "parenttype": "LMS Event"},
			pluck="parent",
		)
		existing_name_filter = filters.get("name")
		if existing_name_filter and isinstance(existing_name_filter, list) and existing_name_filter[0] == "in":
			filters["name"] = ["in", list(set(existing_name_filter[1]) & set(matching_events))]
		else:
			filters["name"] = ["in", matching_events]
		del filters["category"]

	batches = frappe.get_all(
		"LMS Event",
		filters=filters,
		fields=[
			"name",
			"title",
			"description",
			"seat_count",
			"paid_event",
			"amount",
			"amount_usd",
			"currency",
			"start_date",
			"end_date",
			"start_time",
			"end_time",
			"timezone",
			"published",
			"credit_hours",
			"event_type",
			"venue",
			"early_bird_amount",
			"early_bird_amount_usd",
			"early_bird_deadline",
		],
		order_by=order_by,
		start=start,
		page_length=20,
	)

	batches = filter_batches_based_on_start_time(batches, filters)
	batches = attach_event_categories(batches)
	batches = attach_event_days(batches)
	batches = get_batch_card_details(batches)
	return batches


def attach_event_categories(batches: list) -> list:
	"""Pull all category rows for the visible events in one query and
	bucket them per event. Empty list when an event has none."""
	if not batches:
		return batches
	event_names = [b.name for b in batches]
	rows = frappe.get_all(
		"LMS Event Category",
		filters={"parent": ["in", event_names], "parenttype": "LMS Event"},
		fields=["parent", "category"],
		order_by="idx",
	)
	by_event = {}
	for row in rows:
		by_event.setdefault(row.parent, []).append(row.category)
	for batch in batches:
		batch["categories"] = by_event.get(batch.name, [])
	return batches


def attach_event_days(batches: list) -> list:
	"""Pull all per-day rows for the visible events in one query."""
	if not batches:
		return batches
	event_names = [b.name for b in batches]
	rows = frappe.get_all(
		"LMS Event Day",
		filters={"parent": ["in", event_names], "parenttype": "LMS Event"},
		fields=["parent", "date", "start_time", "end_time", "idx"],
		order_by="idx",
	)
	by_event = {}
	for row in rows:
		by_event.setdefault(row.parent, []).append({
			"date": row.date,
			"start_time": row.start_time,
			"end_time": row.end_time,
		})
	for batch in batches:
		batch["event_days"] = by_event.get(batch.name, [])
	return batches


# Alias for frontend compatibility (Batch→Event rename)
get_events = get_batches


def filter_batches_based_on_start_time(batches: list, filters: dict) -> list:
	batchType = get_batch_type(filters)
	if batchType == "upcoming":
		batches_to_remove = [
			batch
			for batch in batches
			if getdate(batch.start_date) == getdate() and str(batch.start_time) < nowtime()
		]
		batches = [batch for batch in batches if batch not in batches_to_remove]
	elif batchType == "archived":
		batches_to_remove = [
			batch
			for batch in batches
			if getdate(batch.start_date) == getdate() and str(batch.start_time) >= nowtime()
		]
		batches = [batch for batch in batches if batch not in batches_to_remove]
	return batches


def get_batch_type(filters: dict) -> str:
	start_date_filter = filters.get("start_date")
	batchType = None
	if start_date_filter:
		sign = start_date_filter[0]
		if ">" in sign:
			batchType = "upcoming"
		elif "<" in sign:
			batchType = "archived"

	return batchType


def get_batch_card_details(batches: list) -> list:
	for batch in batches:
		batch.instructors = get_instructors("LMS Event", batch.name)
		students_count = frappe.db.count("LMS Event Registration", {"event": batch.name})

		if batch.seat_count:
			batch.seats_left = batch.seat_count - students_count

		if batch.paid_event and batch.start_date >= getdate():
			batch.amount, batch.currency = check_multicurrency(
				batch.amount, batch.currency, None, batch.amount_usd
			)
			batch.price = fmt_money(batch.amount, 0, batch.currency)

	return batches


def get_palette(full_name: str) -> list:
	"""
	Returns a color unique to each member for Avatar"""

	palette = [
		["--orange-avatar-bg", "--orange-avatar-color"],
		["--pink-avatar-bg", "--pink-avatar-color"],
		["--blue-avatar-bg", "--blue-avatar-color"],
		["--green-avatar-bg", "--green-avatar-color"],
		["--dark-green-avatar-bg", "--dark-green-avatar-color"],
		["--red-avatar-bg", "--red-avatar-color"],
		["--yellow-avatar-bg", "--yellow-avatar-color"],
		["--purple-avatar-bg", "--purple-avatar-color"],
		["--gray-avatar-bg", "--gray-avatar-color0"],
	]

	encoded_name = str(full_name).encode("utf-8")
	hash_name = hashlib.md5(encoded_name).hexdigest()
	idx = cint((int(hash_name[4:6], 16) + 1) / 5.33)
	return palette[idx % 8]


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=500, seconds=60 * 60)
def get_related_courses(course: str) -> list:
	if not guest_access_allowed():
		return []

	related_course_details = []
	related_courses = frappe.get_all("Related Courses", {"parent": course}, order_by="idx", pluck="course")

	for related_course in related_courses:
		related_course_details.append(get_course_details(related_course))
	return related_course_details


def persona_captured():
	frappe.db.set_single_value("LMS Settings", "persona_captured", 1)


def validate_discussion_reply(doc: Document, method: str):
	topic = frappe.db.get_value(
		"Discussion Topic", doc.topic, ["reference_doctype", "reference_docname"], as_dict=True
	)

	if topic.reference_doctype == "Course Lesson":
		validate_course_access(topic.reference_docname)

	elif topic.reference_doctype == "LMS Event":
		validate_batch_access(topic.reference_docname)


def validate_course_access(lesson: str):
	if not frappe.db.exists("Course Lesson", lesson):
		frappe.throw(_("The lesson does not exist."))

	if has_moderator_role():
		return

	course = frappe.db.get_value("Course Lesson", lesson, "course")
	enrollment_exists = frappe.db.exists("LMS Enrollment", {"member": frappe.session.user, "course": course})
	if not enrollment_exists:
		frappe.throw(_("You do not have access to this course."))


def validate_batch_access(batch: str):
	if not frappe.db.exists("LMS Event", batch):
		frappe.throw(_("The event does not exist."))

	if has_moderator_role():
		return

	enrollment_exists = frappe.db.exists(
		"LMS Event Registration", {"member": frappe.session.user, "event": batch}
	)
	if not enrollment_exists:
		frappe.throw(_("You do not have access to this event."))


def can_modify_course(course: str) -> bool:
	is_instructor = frappe.db.exists(
		"Course Instructor",
		{"instructor": frappe.session.user, "parent": course, "parenttype": "LMS Course"},
	)
	if not (has_moderator_role() or is_instructor):
		return False
	return True


def can_modify_event(batch: str) -> bool:
	roles = frappe.get_roles()
	if any(role in roles for role in LMS_MODERATOR_ROLES):
		return True
	is_instructor = frappe.db.exists(
		"Course Instructor",
		{
			"instructor": frappe.session.user,
			"parent": batch,
			"parenttype": "LMS Event",
		},
	)
	return bool(is_instructor)


def has_lms_role():
	roles = frappe.get_roles()
	lms_roles = set(LMS_ROLES)
	user_roles = set(roles)
	return not lms_roles.isdisjoint(user_roles)


def recalculate_course_progress(course: str, member: str):
	progress = get_course_progress(course, member)
	membership = frappe.db.get_value(
		"LMS Enrollment",
		{
			"member": member,
			"course": course,
		},
		"name",
	)
	frappe.db.set_value("LMS Enrollment", membership, "progress", progress)
	update_program_progress(member)


def get_field_meta(doctype, fieldnames):
	"""Returns field metadata for 'fieldnames' from 'doctype'"""
	meta = frappe.get_meta(doctype)
	fieldnames_meta = {}

	for fieldname in fieldnames:
		field = meta.get_field(fieldname)
		if field:
			fieldnames_meta[fieldname] = {
				"reqd": field.reqd,
				"default": field.default,
				"description": field.description,
			}

	return fieldnames_meta


def is_demo_course(course: str) -> bool:
	title = frappe.db.get_value("LMS Course", course, "title")
	return title == "A guide to Frappe Learning"

# Copyright (c) 2021, Frappe and contributors
# For license information, please see license.txt

import random

import frappe
from frappe import _
from frappe.desk.doctype.notification_log.notification_log import make_notification_logs
from frappe.utils import cint, flt, today
from frappe.website.website_generator import WebsiteGenerator

from ...utils import (
	ensure_instructors_have_moderator_role,
	generate_slug,
	get_audience_recipients,
	get_average_rating,
	get_instructors,
	get_lesson_count,
	get_lms_route,
	validate_image,
)


class LMSCourse(WebsiteGenerator):
	website = frappe._dict(
		# Path is relative to the app root. Frappe's DocumentPage renderer
		# uses this to resolve the Jinja template; without it, template_path
		# is None and rendering crashes inside Jinja's loader.
		template="templates/generators/lms_course.html",
		condition_field="published",
		page_title_field="title",
	)

	def make_route(self):
		# Public landing URL is /c/<slug>. WebsiteGenerator only invokes this
		# when self.route is unset, so admins can override the path manually
		# if they ever need to.
		return f"c/{self.name}"

	def validate(self):
		# WebsiteGenerator's auto-fill only runs when the doc is already
		# website-published. Courses are usually drafted then published later,
		# so force-fill on every save (mirrors community_event.py).
		if not self.route:
			self.route = self.make_route()
		self.validate_published()
		self.validate_instructors()
		self.validate_video_link()
		self.validate_status()
		self.validate_amount_and_currency()
		self.image = validate_image(self.image)
		self.validate_card_gradient()
		ensure_instructors_have_moderator_role([row.instructor for row in self.instructors or []])

	def validate_published(self):
		if self.published and not self.published_on:
			self.published_on = today()

	def validate_instructors(self):
		if self.is_new() and not self.instructors:
			frappe.get_doc(
				{
					"doctype": "Course Instructor",
					"instructor": self.owner,
					"parent": self.name,
					"parentfield": "instructors",
					"parenttype": "LMS Course",
				}
			).save(ignore_permissions=True)

	def validate_video_link(self):
		if self.video_link and "watch?v=" in self.video_link:
			self.video_link = self.video_link.split("watch?v=")[-1]
		elif self.video_link and "/" in self.video_link:
			self.video_link = self.video_link.split("/")[-1]

	def validate_status(self):
		if self.published:
			self.status = "Approved"

	def validate_amount_and_currency(self):
		if self.paid_course and (cint(self.course_price) < 0 or not self.currency):
			frappe.throw(_("Amount and currency are required for paid courses."))

	def validate_card_gradient(self):
		if not self.image and not self.card_gradient:
			colors = [
				"Red",
				"Blue",
				"Green",
				"Yellow",
				"Orange",
				"Pink",
				"Amber",
				"Violet",
				"Cyan",
				"Teal",
				"Gray",
				"Purple",
			]
			self.card_gradient = random.choice(colors)

	def on_update(self):
		if not self.upcoming and self.has_value_changed("upcoming"):
			self.send_email_to_interested_users()

	def send_email_to_interested_users(self):
		interested_users = frappe.get_all("LMS Course Interest", {"course": self.name}, ["name", "user"])
		subject = self.title + " is available!"
		args = {
			"title": self.title,
			"course_link": get_lms_route(f"courses/{self.name}"),
			"app_name": frappe.db.get_single_value("System Settings", "app_name"),
			"site_url": frappe.utils.get_url(),
		}

		for user in interested_users:
			args["first_name"] = frappe.db.get_value("User", user.user, "first_name")
			frappe.enqueue(
				method="lms.lms.utils.lms_send_template_mail",
				queue="short",
				timeout=300,
				is_async=True,
				recipients=user.user,
				default_subject=subject,
				jinja_template="lms_course_interest",
				args=dict(args),
				template_name="Course Now Available",
				header=[subject, "green"],
			)
			frappe.db.set_value("LMS Course Interest", user.name, "email_sent", True)

	def autoname(self):
		if not self.name:
			self.name = generate_slug(self.title, "LMS Course")

	def __repr__(self):
		return f"<Course#{self.name}>"

	def get_context(self, context):
		"""Populate the public landing page Jinja context.

		Rendered for `/c/<slug>`. The page is reachable by guests, so only
		expose conversion-shaped fields — never admin metadata.
		"""
		if not self.published:
			raise frappe.DoesNotExistError

		context.no_cache = 1
		context.course = self
		context.title = self.title
		context.instructors = get_instructors(self.name)
		context.lesson_count = get_lesson_count(self.name)
		context.chapters = _get_public_chapters(self.name)
		context.rating = flt(get_average_rating(self.name) or 0, 2)
		context.enrollment_count = frappe.db.count(
			"LMS Enrollment", {"course": self.name, "member_type": "Student"}
		) or 0
		# `register_url` is the deep-link the CTA falls through to once a
		# visitor is logged in. The Jinja-side register modal short-circuits
		# this for guests.
		context.register_url = f"/lms/courses/{self.name}"


def _get_public_chapters(course: str) -> list:
	"""Lightweight chapter+lesson summary for the public landing page.

	Avoids the heavier `get_course_outline` because we only need titles and
	counts here — no progress data, no SCORM details.
	"""
	chapter_refs = frappe.get_all(
		"Chapter Reference", {"parent": course}, ["chapter", "idx"], order_by="idx"
	)
	chapters = []
	for ref in chapter_refs:
		chapter = frappe.db.get_value(
			"Course Chapter", ref.chapter, ["name", "title"], as_dict=True
		)
		if not chapter:
			continue
		chapter["idx"] = ref.idx
		chapter["lesson_count"] = frappe.db.count("Lesson Reference", {"parent": chapter.name})
		chapters.append(chapter)
	return chapters


def send_notification_for_published_courses():
	send_notification = frappe.db.get_single_value("LMS Settings", "send_notification_for_published_courses")
	if not send_notification:
		return

	courses_published_today = frappe.get_all(
		"LMS Course",
		{
			"published_on": today(),
			"notification_sent": 0,
		},
		["name", "title", "short_introduction", "audience"],
	)

	if not courses_published_today:
		return

	if send_notification == "Email":
		send_email_notification_for_published_courses(courses_published_today)
	else:
		send_system_notification_for_published_courses(courses_published_today)


def send_email_notification_for_published_courses(courses):
	brand_name = frappe.db.get_single_value("Website Settings", "app_name")
	brand_logo = frappe.db.get_single_value("Website Settings", "banner_image")
	subject = _("A new course has been published on {0}").format(brand_name)
	template = "published_course_notification"

	for course in courses:
		instructors = get_instructors("LMS Course", course.name)
		students = get_audience_recipients(course.audience, extra_users=instructors)

		args = {
			"brand_logo": brand_logo,
			"brand_name": brand_name,
			"title": course.title,
			"short_introduction": course.short_introduction,
			"instructors": instructors,
			"course_url": frappe.utils.get_url(get_lms_route(f"courses/{course.name}")),
		}

		from lms.lms.utils import lms_send_template_mail

		lms_send_template_mail(
			recipients=instructors,
			default_subject=subject,
			jinja_template=template,
			args=args,
			template_name="New Course Published",
			bcc=students,
		)
		frappe.db.set_value("LMS Course", course.name, "notification_sent", 1)


def send_system_notification_for_published_courses(courses):
	for course in courses:
		instructors = frappe.get_all("Course Instructor", {"parent": course.name}, pluck="instructor")
		students = get_audience_recipients(course.audience, extra_users=instructors)
		instructor_name = (
			frappe.db.get_value("User", instructors[0], "full_name") if instructors else ""
		)
		notification = frappe._dict(
			{
				"subject": _("{0} has published a new course {1}").format(
					frappe.bold(instructor_name), frappe.bold(course.title)
				),
				"email_content": _(
					"A new course '{0}' has been published that might interest you. Check it out!"
				).format(course.title),
				"document_type": "LMS Course",
				"document_name": course.name,
				"from_user": instructors[0] if instructors else None,
				"type": "Alert",
				"link": get_lms_route(f"courses/{course.name}"),
			}
		)
		make_notification_logs(notification, students)
		frappe.db.set_value("LMS Course", course.name, "notification_sent", 1)


def update_course_statistics():
	courses = frappe.get_all("LMS Course", fields=["name"])

	for course in courses:
		lessons = get_lesson_count(course.name)

		enrollments = frappe.db.count("LMS Enrollment", {"course": course.name, "member_type": "Student"})

		avg_rating = get_average_rating(course.name) or 0
		avg_rating = flt(avg_rating, frappe.get_system_settings("float_precision") or 3)

		frappe.db.set_value(
			"LMS Course",
			course.name,
			{"lessons": lessons, "enrollments": enrollments, "rating": avg_rating},
		)

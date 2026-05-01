"""Seed Email Template records for transactional flows so admins can edit
them in /lms Settings → Email Templates without a code deploy.

Idempotent: existing records (by name) are left untouched. New records start
with subject + body that match the current Jinja file output so behavior is
unchanged on first migrate. The runtime helper `lms_send_template_mail`
falls back to the Jinja file when no DB record exists, so this patch is
safe even if a record fails to insert.
"""

import frappe


# Each entry: name → {subject, response_html}
# Bodies are cleaned-up versions of lms/templates/emails/*.html. Admins can
# rewrite them; the helper renders these via frappe.render_template with the
# same args dict the Jinja files expect.
TEMPLATES = {
	"Mention Notification": {
		"subject": "{{ sender }} mentioned you in a comment",
		"response_html": (
			"""<p>{{ sender }} mentioned you in a comment.</p>
<blockquote>{{ content }}</blockquote>
<p><a href="{{ link }}">View discussion</a></p>"""
		),
	},
	"Event Starting Tomorrow": {
		"subject": "Your event {{ title }} is starting tomorrow",
		"response_html": (
			"""<p>Hi {{ student_name }},</p>
<p>Your event is scheduled for tomorrow. Please be prepared and join on time.</p>
<p><b>Event:</b> {{ title }}</p>
<p><b>Date:</b> {{ frappe.utils.format_date(date, "long") }}</p>
<p><b>Time:</b> {{ frappe.utils.format_time(time, "hh:mm a") }}</p>
{% if zoom_link %}
<p>
  <a href="{{ zoom_link }}" style="display:inline-block;padding:10px 20px;background:#2563eb;color:#fff;text-decoration:none;border-radius:6px;font-weight:600;">Join Webinar</a>
</p>
<p style="font-size:12px;color:#6b7280;">Or copy this link: <a href="{{ zoom_link }}">{{ zoom_link }}</a></p>
{% endif %}
<p><a href="{{ get_lms_route('events/' ~ name) }}">View event details</a></p>
<p>If you have any questions, reply to this email and we will be in touch.</p>"""
		),
	},
	"Event Starting in One Hour": {
		"subject": "Your event {{ title }} starts in about an hour",
		"response_html": (
			"""<p>Hi {{ student_name }},</p>
<p>Your event is starting in about an hour. Time to get ready!</p>
<p><b>Event:</b> {{ title }}</p>
<p><b>Date:</b> {{ frappe.utils.format_date(date, "long") }}</p>
<p><b>Time:</b> {{ frappe.utils.format_time(time, "hh:mm a") }}</p>
{% if zoom_link %}
<p>
  <a href="{{ zoom_link }}" style="display:inline-block;padding:12px 24px;background:#2563eb;color:#fff;text-decoration:none;border-radius:6px;font-weight:600;">Join Webinar</a>
</p>
<p style="font-size:12px;color:#6b7280;">Or copy this link: <a href="{{ zoom_link }}">{{ zoom_link }}</a></p>
{% endif %}
<p><a href="{{ get_lms_route('events/' ~ name) }}">View event details</a></p>
<p>See you there!</p>"""
		),
	},
	"Live Class Reminder": {
		"subject": "Your class on {{ title }} is today",
		"response_html": (
			"""<p>Hi {{ student_name }},</p>
<p>You have a live class scheduled today. Please be prepared and join on time.</p>
<p><b>Class:</b> {{ title }}</p>
<p><b>Date:</b> {{ frappe.utils.format_date(date, "long") }}</p>
<p><b>Time:</b> {{ frappe.utils.format_time(time, "hh:mm a") }}</p>
<p>If you have any questions, reply to this email and we will be in touch.</p>"""
		),
	},
	"New Event Published": {
		"subject": "A new event has been published on {{ brand_name }}",
		"response_html": (
			"""<p>Hello,</p>
<p>A new event has been published on {{ brand_name }} that might interest you.</p>
<p><b>{{ title }}</b></p>
<p>{{ short_introduction }}</p>
<p><a href="{{ batch_url }}" style="display:inline-block;padding:8px 16px;background:#171717;color:#fff;text-decoration:none;border-radius:6px;">View event</a></p>"""
		),
	},
	"New Course Published": {
		"subject": "A new course has been published on {{ brand_name }}",
		"response_html": (
			"""<p>Hello,</p>
<p>A new course has been published on {{ brand_name }} that might interest you.</p>
<p><b>{{ title }}</b></p>
<p>{{ short_introduction }}</p>
<p><a href="{{ course_url }}" style="display:inline-block;padding:8px 16px;background:#171717;color:#fff;text-decoration:none;border-radius:6px;">View course</a></p>"""
		),
	},
	"Course Now Available": {
		"subject": "{{ title }} is available!",
		"response_html": (
			"""<p>Hi {{ first_name }},</p>
<p>The course <b>{{ title }}</b> is now available on {{ app_name }}.</p>
<p><a href="{{ course_link }}" style="display:inline-block;padding:8px 16px;background:#171717;color:#fff;text-decoration:none;border-radius:6px;">Start Learning</a></p>
<p>Or copy this link in your browser: <a href="{{ course_link }}">{{ site_url }}{{ course_link }}</a></p>
<p>Thanks,<br>{{ app_name }}</p>"""
		),
	},
}


def execute():
	for name, body in TEMPLATES.items():
		if frappe.db.exists("Email Template", name):
			continue
		doc = frappe.new_doc("Email Template")
		doc.name = name
		doc.subject = body["subject"]
		doc.use_html = 1
		doc.response_html = body["response_html"]
		doc.flags.ignore_permissions = True
		doc.insert()

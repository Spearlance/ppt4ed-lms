"""Seed the "Event Starting in 15 Minutes" Email Template so admins can edit
the copy at /lms Settings -> Email Templates without a code deploy.

Idempotent: skipped if a record with the same name already exists. The
runtime helper `lms_send_template_mail` falls back to the
`event_starting_in_15_minutes.html` Jinja file when no DB record exists,
so this patch is safe even if the insert is skipped.
"""

import frappe


TEMPLATE_NAME = "Event Starting in 15 Minutes"
SUBJECT = "Your event {{ title }} starts in 15 minutes"
RESPONSE_HTML = """<p>Hi {{ student_name }},</p>
<p>Your event starts in about 15 minutes. Time to log in!</p>
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
<p>See you there!</p>
"""


def execute():
	if frappe.db.exists("Email Template", TEMPLATE_NAME):
		return
	doc = frappe.new_doc("Email Template")
	doc.name = TEMPLATE_NAME
	doc.subject = SUBJECT
	doc.use_html = 1
	doc.response_html = RESPONSE_HTML
	doc.flags.ignore_permissions = True
	doc.insert()

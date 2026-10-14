"""Seed the "Event Registration Confirmation" Email Template so admins can edit
the copy at /lms Settings -> Email Templates without a code deploy.

Mirrors seed_course_enrollment_confirmation_template: same receipt block
(amount, payment reference, purchase date) so a paid event registration gets
the same receipt a paid course enrollment does.

Idempotent: skipped if a record with the same name already exists. The runtime
helper `lms_send_template_mail` falls back to the
`event_enrollment_confirmation.html` Jinja file when no DB record exists.
"""

import frappe


TEMPLATE_NAME = "Event Registration Confirmation"
SUBJECT = "Enrollment Confirmation for {{ title }}"
RESPONSE_HTML = """<p>Hi {{ first_name or student_name }},</p>
<p>You're registered! This email confirms your registration for the event below.</p>
<p><b>Event:</b> {{ title }}</p>
<p><b>Date:</b> {{ event_date_display }}</p>
<p><b>Time:</b> {{ event_time_display }}</p>
{% if amount_display %}
<p><b>Amount paid:</b> {{ amount_display }}</p>
<p><b>Payment reference:</b> {{ payment_reference }}</p>
<p><b>Purchase date:</b> {{ purchase_date }}</p>
<p style="font-size:12px;color:#6b7280;">Please keep this email as your receipt.</p>
{% endif %}
{% if zoom_link %}
<p style="font-size:14px;color:#374151;">Save this link for the day of the event:</p>
<p>
  <a href="{{ zoom_link }}" style="display:inline-block;padding:10px 20px;background:#2563eb;color:#fff;text-decoration:none;border-radius:6px;font-weight:600;">Webinar Link</a>
</p>
<p style="font-size:12px;color:#6b7280;">Or copy this link: <a href="{{ zoom_link }}">{{ zoom_link }}</a></p>
{% endif %}
<p><a href="{{ event_url }}">Visit your event page</a></p>
<p>We'll send a reminder closer to the date. If you have any questions, just reply to this email.</p>
<p>Best regards,<br>PPT4Ed</p>
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

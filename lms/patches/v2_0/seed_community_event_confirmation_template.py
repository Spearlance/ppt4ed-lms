"""Seed the Community Event Confirmation Email Template so admins can edit
the wrapper copy without a code deploy.

Idempotent: skipped if a record with the same name already exists. The
runtime helper `lms_send_template_mail` falls back to the
`community_event_confirmation.html` Jinja file when no DB record exists, so
this patch is safe even if the insert is skipped.
"""

import frappe


TEMPLATE_NAME = "Community Event Confirmation"
SUBJECT = "You're registered for {{ event_title }}"
RESPONSE_HTML = """<p>Hi {{ guardian_name }},</p>
<p>You're registered! We can't wait to see you at the event.</p>
<div style="background-color: #F8F8F8; border-radius: 12px; padding: 16px; margin: 16px 0;">
  <p style="margin: 0 0 6px;"><b>Event:</b> {{ event_title }}</p>
  <p style="margin: 0 0 6px;"><b>Date:</b> {{ frappe.utils.format_date(event_date, "long") }}{% if event_end_date and event_end_date != event_date %} &mdash; {{ frappe.utils.format_date(event_end_date, "long") }}{% endif %}</p>
  {% if event_time %}<p style="margin: 0 0 6px;"><b>Time:</b> {{ frappe.utils.format_time(event_time, "hh:mm a") }}{% if event_end_time %} &ndash; {{ frappe.utils.format_time(event_end_time, "hh:mm a") }}{% endif %}</p>{% endif %}
  {% if location %}<p style="margin: 0 0 6px;"><b>Location:</b> {{ location }}</p>{% endif %}
  {% if virtual_link %}<p style="margin: 0;"><b>Join:</b> <a href="{{ virtual_link }}">{{ virtual_link }}</a></p>{% endif %}
</div>
<p style="margin: 16px 0 4px;"><b>Attendees ({{ attendee_count }}):</b></p>
<ul>
  {% for n in attendee_names %}<li>{{ n }}</li>{% endfor %}
</ul>
{% if donation_total and donation_total > 0 %}
<p>Thank you for your ${{ "%.2f"|format(donation_total|float) }} donation to PPT4ed!</p>
{% endif %}
<p>
  <a href="{{ event_url }}" style="display:inline-block;padding:8px 16px;background:#171717;color:#fff;text-decoration:none;border-radius:8px;">View event details</a>
</p>
<p style="color:#6b7280;font-size:12px;margin-top:24px;">If you need to make a change, just reply to this email.</p>
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

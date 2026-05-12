"""Seed the Event Announcement Email Template so admins can edit the wrapper
copy at /lms Settings -> Email Templates without a code deploy.

Idempotent: skipped if a record with the same name already exists. The
runtime helper `lms_send_template_mail` falls back to the
`event_announcement.html` Jinja file when no DB record exists, so this
patch is safe even if the insert is skipped.
"""

import frappe


TEMPLATE_NAME = "Event Announcement"
SUBJECT = "[{{ event_title }}] {{ announcement_subject }}"
RESPONSE_HTML = """<p style="font-size: 16px; font-weight: 600; margin-bottom: 4px;">Announcement from {{ instructor_name }}</p>
<p style="color: #6b7280; margin-top: 0;">{{ event_title }}</p>
<div style="background-color: #F8F8F8; border-radius: 12px; padding: 16px; margin: 16px 0;">
  <div style="font-weight: 600; margin-bottom: 8px;">{{ announcement_subject }}</div>
  <div style="line-height: 1.5;">{{ announcement_body }}</div>
</div>
<p>
  <a href="{{ event_url }}" style="display:inline-block;padding:8px 16px;background:#0b6685;color:#fff;text-decoration:none;border-radius:8px;">Open event</a>
</p>
<p style="color:#6b7280;font-size:12px;margin-top:24px;">You're receiving this because you're enrolled in {{ event_title }} on {{ brand_name }}.</p>
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

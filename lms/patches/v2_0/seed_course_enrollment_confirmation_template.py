"""Seed the "Course Enrollment Confirmation" Email Template so admins can edit
the copy at /lms Settings -> Email Templates without a code deploy.

Idempotent: skipped if a record with the same name already exists. The
runtime helper `lms_send_template_mail` falls back to the
`course_enrollment_confirmation.html` Jinja file when no DB record exists,
so this patch is safe even if the insert is skipped.
"""

import frappe


TEMPLATE_NAME = "Course Enrollment Confirmation"
SUBJECT = "Enrollment Confirmation for {{ course_title }}"
RESPONSE_HTML = """<p>Hi {{ first_name }},</p>
<p>You're enrolled! This email confirms your enrollment in the course below.</p>
<p><b>Course:</b> {{ course_title }}</p>
{% if amount_display %}
<p><b>Amount paid:</b> {{ amount_display }}</p>
<p><b>Payment reference:</b> {{ payment_reference }}</p>
<p><b>Date:</b> {{ purchase_date }}</p>
<p style="font-size:12px;color:#6b7280;">Please keep this email as your receipt.</p>
{% elif ceu_hours %}
<p><b>CEU hours used:</b> {{ ceu_hours }} ({{ credit_source }})</p>
<p><b>Date:</b> {{ purchase_date }}</p>
{% endif %}
<p>
  <a href="{{ course_url }}" style="display:inline-block;padding:10px 20px;background:#2563eb;color:#fff;text-decoration:none;border-radius:6px;font-weight:600;">Start Learning</a>
</p>
<p>If you have any questions, just reply to this email.</p>
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

"""Seed Email Template records for the three invite/welcome flows so admins
can edit them in /lms Settings → Email Templates without a code deploy.

Idempotent: skipped if a record with the same name already exists. The
runtime helper `lms_send_template_mail` falls back to the matching Jinja
file when no DB record exists, so this patch is safe even if an insert is
skipped.
"""

import frappe


TEMPLATES = {
	"Company Member Invite": {
		"subject": "You're invited to join {{ company_name }} on PPT4ed",
		"response_html": (
			"""<p>Hi there,</p>
<p>{{ inviter_name }} has invited you to join <b>{{ company_name }}</b> on PPT4ed.</p>
<p>Your company plan covers continuing-education courses, live events, and resources.
Click below to accept the invitation and either sign in or create your free account.</p>
<p>
  <a href="{{ accept_url }}" style="display:inline-block;padding:12px 24px;background:#171717;color:#fff;text-decoration:none;border-radius:8px;font-weight:600;">Accept invitation</a>
</p>
<p style="font-size:12px;color:#6b7280;">Or copy this link into your browser: <a href="{{ accept_url }}">{{ accept_url }}</a></p>
{% if expires_on %}
<p style="font-size:12px;color:#6b7280;">This invitation expires on {{ frappe.utils.format_datetime(expires_on, "MMM d, yyyy") }}.</p>
{% endif %}
<p>Questions? Reply to this email or write to support@ppt4ed.org.</p>"""
		),
	},
	"Company Admin Invite": {
		"subject": "You're invited to manage {{ company_name }} on PPT4ed",
		"response_html": (
			"""<p>Hi there,</p>
<p>{{ inviter_name }} has invited you to manage <b>{{ company_name }}</b> on PPT4ed.</p>
<p>As a company admin, you'll be able to invite members, allocate continuing-education credits,
review enrollment requests, and oversee billing for your team.</p>
<p>Click below to accept the invitation and either sign in or create your account.</p>
<p>
  <a href="{{ accept_url }}" style="display:inline-block;padding:12px 24px;background:#171717;color:#fff;text-decoration:none;border-radius:8px;font-weight:600;">Accept and set up your account</a>
</p>
<p style="font-size:12px;color:#6b7280;">Or copy this link into your browser: <a href="{{ accept_url }}">{{ accept_url }}</a></p>
{% if expires_on %}
<p style="font-size:12px;color:#6b7280;">This invitation expires on {{ frappe.utils.format_datetime(expires_on, "MMM d, yyyy") }}.</p>
{% endif %}
<p>Questions? Reply to this email or write to support@ppt4ed.org.</p>"""
		),
	},
	"LMS Member Welcome": {
		"subject": "Welcome to PPT4ed, {{ first_name }}",
		"response_html": (
			"""<p>Hi {{ first_name }},</p>
<p>{{ inviter_name }} has added you to PPT4ed{% if company %} as part of <b>{{ company }}</b>{% endif %}
as a{% if role_label == "Instructor" %}n{% endif %} {{ role_label.lower() }}.</p>
<p>To get started, set your password and sign in:</p>
<p>
  <a href="{{ setup_url }}" style="display:inline-block;padding:12px 24px;background:#171717;color:#fff;text-decoration:none;border-radius:8px;font-weight:600;">Set password and sign in</a>
</p>
<p style="font-size:12px;color:#6b7280;">Or copy this link into your browser: <a href="{{ setup_url }}">{{ setup_url }}</a></p>
<p>Once signed in, your dashboard at PPT4ed will show your enrolled courses, upcoming events,
and certificates as you earn them.</p>
<p>Questions? Reply to this email or write to support@ppt4ed.org.</p>"""
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

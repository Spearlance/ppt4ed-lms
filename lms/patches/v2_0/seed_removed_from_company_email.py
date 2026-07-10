"""Seed the 'Removed from Company' Email Template so admins can edit the
copy that goes out when a member is removed from a Company Account.

Idempotent: skipped if the record already exists. Runtime helper
`lms_send_template_mail` falls back to the Jinja file if the record is
missing, so this patch is safe to re-run or skip.
"""

import frappe


TEMPLATE_NAME = "Removed from Company"

SUBJECT = "You've been removed from {{ company_name }} on PPT4ed"

RESPONSE_HTML = """<p>Hi {{ first_name }},</p>

<p>You've been removed from <b>{{ company_name }}</b> on PPT4ed.</p>

<p>The good news: <b>your PPT4ed account is still active</b>. Your earned certificates,
quiz history, and personal enrollments stay with you.</p>

<p>To keep earning continuing-education credits, you can:</p>
<ul>
  <li>Sign in any time to access your past certificates and resources.</li>
  <li>Purchase courses or events individually with a personal payment method.</li>
  <li>Join another company plan if a new employer enrolls you.</li>
</ul>

<p>
  <a href="{{ login_url }}" style="display:inline-block;padding:10px 20px;background:#0b6685;color:#fff;text-decoration:none;border-radius:6px;font-weight:600;">Sign in to PPT4ed</a>
</p>

<p style="font-size:12px;color:#6b7280;">Or copy this link: <a href="{{ login_url }}">{{ login_url }}</a></p>

<p>Questions? Reply to this email or write to info@ppt4ed.org.</p>"""


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

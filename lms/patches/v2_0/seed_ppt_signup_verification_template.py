"""Seed the Email Template record for the PPT signup verification flow so
admins can edit copy via /lms Settings → Email Templates without a deploy.

`lms_send_template_mail` falls back to the matching Jinja file when no DB
record exists, so this patch is safe to skip if the row already exists.
"""

import frappe


def execute():
	name = "PPT Signup Verification"
	if frappe.db.exists("Email Template", name):
		return

	doc = frappe.new_doc("Email Template")
	doc.name = name
	doc.subject = "Verify your PPT4Ed email to finish signing up"
	doc.use_html = 1
	doc.response_html = """<p>Hi {{ first_name }},</p>
<p>You're almost in. To finish creating your PPT4Ed account, confirm that this inbox is yours:</p>
<p>
  <a href="{{ verify_url }}" style="display:inline-block;padding:12px 24px;background:#171717;color:#fff;text-decoration:none;border-radius:8px;font-weight:600;">Verify email and continue</a>
</p>
<p style="font-size:12px;color:#6b7280;">Or copy this link into your browser: <a href="{{ verify_url }}">{{ verify_url }}</a></p>
<p style="font-size:13px;color:#6b7280;">This link expires in {{ expires_minutes }} minutes. If you didn't try to sign up for PPT4Ed, you can safely ignore this email — no account has been created.</p>"""
	doc.flags.ignore_permissions = True
	doc.insert()

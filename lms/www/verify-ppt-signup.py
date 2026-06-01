"""Email-verification landing for PPT-domain signups.

When a guest signs up via `signup_and_enroll` with a @ppt4ed.com or
@ppt4kids.com email, no User is created — the signup data is held in a
PPT Enrollment Verification row and a link to /verify-ppt-signup?token=...
is mailed to the address. Clicking that link runs this page, which delegates
to `_consume_ppt_signup_token` for the actual work and then redirects to
wherever the helper points us.
"""

import frappe


def get_context(context):
	context.no_cache = 1
	token = (frappe.form_dict.get("token") or "").strip()

	from lms.lms.api import _consume_ppt_signup_token

	frappe.local.flags.redirect_location = _consume_ppt_signup_token(token)
	raise frappe.Redirect

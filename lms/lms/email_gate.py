"""Block outbound mail to non-allowlisted recipients on dev sites.

Mirrors the hostname allowlist in `lms/public/js/dev_login.js` so dev test
enrollments can't email real client addresses. Prod is a hard no-op.
"""

import fnmatch

import frappe

DEV_SITES = {"devlms.ppt4ed.org", "localhost", "127.0.0.1"}

DEFAULT_ALLOWED_PATTERNS = ("*@test.com", "*@e2e.invalid")


def _is_dev_site() -> bool:
	return getattr(frappe.local, "site", None) in DEV_SITES


def _allowed_patterns() -> tuple[str, ...]:
	extra = frappe.conf.get("dev_email_allowlist") or ()
	return DEFAULT_ALLOWED_PATTERNS + tuple(extra)


def _is_allowed(recipient: str | None) -> bool:
	if not recipient:
		return True
	addr = recipient.strip().lower()
	return any(fnmatch.fnmatchcase(addr, p) for p in _allowed_patterns())


def block_outbound_on_dev(doc, method=None):
	"""Email Queue before_insert hook.

	On dev sites, drop recipients outside the allowlist. If no recipients
	remain, cancel the queue entry so the worker skips it. Always log
	what was blocked to Error Log for audit.

	Failsafe: any unexpected exception inside the gate is swallowed (and
	logged) so a bug here can never break the email pipeline — and via the
	pipeline, every after_insert that calls frappe.sendmail (e.g. the Stripe
	webhook → LMS Event Registration → send_confirmation_email chain).
	"""
	try:
		if not _is_dev_site():
			return

		original = list(doc.recipients or [])
		kept = [r for r in original if _is_allowed(r.recipient)]
		blocked = [r.recipient for r in original if not _is_allowed(r.recipient)]

		if not blocked:
			return

		doc.recipients = kept
		if not kept:
			doc.status = "Cancelled"

		# Email Queue has no `subject` field — the subject lives in the MIME
		# headers of `message`. Use reference_doctype/reference_name instead;
		# they're proper top-level fields and more useful for tracing what
		# triggered the send.
		ref_doctype = getattr(doc, "reference_doctype", None)
		ref_name = getattr(doc, "reference_name", None)
		frappe.log_error(
			message=(
				f"site={frappe.local.site} "
				f"reference={ref_doctype}/{ref_name} "
				f"blocked={blocked} kept={[r.recipient for r in kept]}"
			),
			title="Dev Email Gate: blocked outbound recipients",
		)
	except Exception:
		try:
			frappe.log_error(title="Dev Email Gate: hook crashed (failed open)")
		except Exception:
			pass

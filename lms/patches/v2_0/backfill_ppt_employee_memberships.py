import frappe


def execute():
	"""Backfill PPT Employee CEU Memberships for every existing PPT-domain user.

	Before this patch the only code path that minted memberships for PPT staff
	was the admin "Add New Member" modal (lms.lms.api.invite_lms_member). Users
	who created their own account via the public Register modal, the legacy
	/signup form, or the Frappe Desk got nothing — so they were prompted to pay
	on paid courses/events even though the policy is free access.

	Going forward User.after_insert mints automatically. This one-time pass
	covers the pre-fix backlog. Idempotent: skips users who already have an
	active membership row.
	"""
	from lms.lms.api import _is_ppt_employee_email, _mint_ppt_employee_membership

	emails = frappe.get_all(
		"User",
		filters={"enabled": 1, "name": ["not in", ["Administrator", "Guest"]]},
		pluck="name",
	)

	minted = 0
	for email in emails:
		if not _is_ppt_employee_email(email):
			continue
		if frappe.db.exists(
			"CEU Membership",
			{"member": email, "membership_type": "PPT Employee", "status": "Active"},
		):
			continue
		try:
			_mint_ppt_employee_membership(email)
			minted += 1
		except Exception:
			frappe.log_error(
				frappe.get_traceback(),
				f"Backfill PPT Employee membership failed for {email}",
			)

	print(f"Backfilled {minted} PPT Employee membership(s)")

import frappe


# Marketing decision (2026-05-18): only Free + Educational Partner show on
# the public Individual tab. Flip `active=0` so existing memberships keep
# working but no new signups land on these tiers.
#
# Filter by DOCNAME, not plan_type. "Educational Partner" currently shares
# plan_type="Professional" with "Professional Membership" — filtering by
# plan_type would also hide Educational Partner, which Marketing wants
# to keep visible.
PLAN_NAMES_TO_HIDE = ("Professional Membership", "Individual Business Membership")


def execute():
	plans = frappe.get_all(
		"CEU Membership Plan",
		filters={"name": ["in", PLAN_NAMES_TO_HIDE], "active": 1},
		pluck="name",
	)
	for plan in plans:
		frappe.db.set_value("CEU Membership Plan", plan, "active", 0)
	frappe.db.commit()

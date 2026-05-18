import frappe


# Marketing decision (2026-05-18): only Free + Educational Partner show on
# the public Individual tab. Flip `active=0` so existing memberships keep
# working but no new signups land on these tiers.
PLAN_TYPES_TO_HIDE = ("Professional", "Individual-Business")


def execute():
	plans = frappe.get_all(
		"CEU Membership Plan",
		filters={"plan_type": ["in", PLAN_TYPES_TO_HIDE], "active": 1},
		pluck="name",
	)
	for plan in plans:
		frappe.db.set_value("CEU Membership Plan", plan, "active", 0)
	frappe.db.commit()

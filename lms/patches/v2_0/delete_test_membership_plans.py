import frappe


# Test plans that leaked into the live database from test runs.
TEST_PLANS = [
    "Invoice Test Plan",
    "Test Pro 20",
    "Credit Test Plan",
    "Enroll Test Plan",
    "Professional 20hr",
    "Webhook Test Plan",
    "Test Professional Plan",
    "Test Admin Professional Plan",
    "Company Webhook Test Plan",
    "Company 100hr",
]


def execute():
    for plan in TEST_PLANS:
        if frappe.db.exists("CEU Membership Plan", plan):
            frappe.delete_doc(
                "CEU Membership Plan", plan, force=True, ignore_permissions=True
            )

    frappe.db.commit()

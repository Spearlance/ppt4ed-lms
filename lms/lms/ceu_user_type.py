import frappe
from frappe import _


@frappe.whitelist()
def get_user_type(user: str | None = None):
    """Determine the user's account type based on their relationships.

    Returns dict with 'type' key: 'company', 'ppt_employee', 'professional', or 'one_off'.
    Also includes relevant context (membership name, company name).
    """
    if not user:
        user = frappe.session.user

    # Check for active company membership first
    company_member = frappe.db.get_value(
        "Company Member",
        {"user": user, "status": "Active", "parenttype": "Company Account"},
        ["parent"],
        as_dict=True
    )
    if company_member:
        company = frappe.get_doc("Company Account", company_member.parent)
        return {
            "type": "company",
            "company": company.name,
            "membership": company.membership,
        }

    # Check for active individual membership (Professional or PPT Employee)
    membership = frappe.db.get_value(
        "CEU Membership",
        {"member": user, "membership_type": ["in", ["Professional", "PPT Employee"]], "status": "Active"},
        ["name", "membership_type"],
        as_dict=True,
    )
    if membership:
        if membership.membership_type == "PPT Employee":
            return {
                "type": "ppt_employee",
                "membership": membership.name,
            }
        return {
            "type": "professional",
            "membership": membership.name,
        }

    # Default: one-off user
    return {
        "type": "one_off",
    }

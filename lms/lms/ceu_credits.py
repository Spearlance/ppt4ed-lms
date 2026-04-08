import frappe
from frappe import _
from frappe.utils import now_datetime


def allocate_credits(membership_name, hours):
    """Add credits to a membership. Used on subscription payment."""
    membership = frappe.get_doc("CEU Membership", membership_name)
    membership.credit_balance += hours
    membership.save(ignore_permissions=True)

    frappe.get_doc({
        "doctype": "CEU Credit Ledger",
        "membership": membership_name,
        "user": membership.member,
        "transaction_type": "Allocation",
        "hours": hours,
        "balance_after": membership.credit_balance,
        "timestamp": now_datetime()
    }).insert(ignore_permissions=True)


def debit_credits(membership_name, user, hours, course=None):
    """Debit credits from a membership. Used on enrollment."""
    membership = frappe.get_doc("CEU Membership", membership_name)

    if membership.status != "Active":
        frappe.throw(_("Membership is not active"), frappe.ValidationError)

    if membership.credit_balance < hours:
        frappe.throw(
            _("Insufficient credits. Available: {0}, Required: {1}").format(
                membership.credit_balance, hours
            ),
            frappe.ValidationError
        )

    membership.credit_balance -= hours
    membership.save(ignore_permissions=True)

    frappe.get_doc({
        "doctype": "CEU Credit Ledger",
        "membership": membership_name,
        "user": user,
        "course": course,
        "transaction_type": "Enrollment",
        "hours": -hours,
        "balance_after": membership.credit_balance,
        "timestamp": now_datetime()
    }).insert(ignore_permissions=True)

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
    """Debit credits from a membership. Uses pessimistic locking for concurrency safety."""
    # Lock the row — prevents concurrent reads until this transaction commits
    locked_balance = frappe.db.sql(
        "SELECT credit_balance FROM `tabCEU Membership` WHERE name=%s FOR UPDATE",
        membership_name,
        as_dict=True
    )

    if not locked_balance:
        frappe.throw(_("Membership not found"), frappe.ValidationError)

    current_balance = locked_balance[0].credit_balance

    membership = frappe.get_doc("CEU Membership", membership_name)

    if membership.status != "Active":
        frappe.throw(_("Membership is not active"), frappe.ValidationError)

    if current_balance < hours:
        frappe.throw(
            _("Insufficient credits. Available: {0}, Required: {1}").format(
                current_balance, hours
            ),
            frappe.ValidationError
        )

    membership.credit_balance = current_balance - hours
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

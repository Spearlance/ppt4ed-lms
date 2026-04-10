"""
Seed test users for manual QA of enrollment flows.

Usage:
    bench execute lms.lms.seed_test_users.seed

Personas:
    pro@test.com            — Professional membership, 20 credits
    company-admin@test.com  — Company membership (Sunrise Therapy Group admin), 80 credits
    company-employee@test.com — No membership, uses company pool
    ppt@test.com            — PPT Employee membership, 0 credits (free access)
    broke@test.com          — Professional membership, 0.5 credits (insufficient)

All users: password=password123, role=LMS Student
Idempotent — safe to run multiple times.
"""

import frappe
from frappe.utils import today, now_datetime, add_years


USERS = [
    {
        "email": "pro@test.com",
        "first_name": "Sarah",
        "last_name": "Professional",
        "membership": {
            "plan": "Professional Membership",
            "membership_type": "Professional",
            "credit_balance": 20.0,
        },
    },
    {
        "email": "company-admin@test.com",
        "first_name": "Mike",
        "last_name": "Manager",
        "membership": {
            "plan": "Growth Partner",
            "membership_type": "Company",
            "credit_balance": 80.0,
        },
    },
    {
        "email": "company-employee@test.com",
        "first_name": "Lisa",
        "last_name": "Employee",
        "membership": None,
    },
    {
        "email": "ppt@test.com",
        "first_name": "Pat",
        "last_name": "PPTEmployee",
        "membership": {
            "plan": "PPT Employee Plan",
            "membership_type": "PPT Employee",
            "credit_balance": 0.0,
        },
    },
    {
        "email": "broke@test.com",
        "first_name": "Brooke",
        "last_name": "Nocredits",
        "membership": {
            "plan": "Professional Membership",
            "membership_type": "Professional",
            "credit_balance": 0.5,
        },
    },
]

COMPANY = {
    "company_name": "Sunrise Therapy Group",
    "admin_email": "company-admin@test.com",
    "member_emails": ["company-admin@test.com", "company-employee@test.com"],
}


def _ensure_ppt_employee_plan():
    """Create the PPT Employee Plan if it doesn't exist in the DB."""
    if frappe.db.exists("CEU Membership Plan", "PPT Employee Plan"):
        print("  [skip] CEU Membership Plan 'PPT Employee Plan' already exists")
        return

    frappe.get_doc({
        "doctype": "CEU Membership Plan",
        "title": "PPT Employee Plan",
        "plan_type": "PPT Employee",
        "ceu_hours": 0,
        "price": 0.0,
        "stripe_price_id": "",
        "active": 1,
        "display_order": 99,
        "is_recommended": 0,
    }).insert(ignore_permissions=True)
    print("  [created] CEU Membership Plan 'PPT Employee Plan'")


def _ensure_user(email, first_name, last_name):
    """Create User if it doesn't exist. Returns the email (Frappe User name)."""
    if frappe.db.exists("User", email):
        print(f"  [skip] User {email} already exists")
        return email

    user = frappe.get_doc({
        "doctype": "User",
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
        "enabled": 1,
        "new_password": "TestUser@2026!",
        "send_welcome_email": 0,
        "roles": [{"role": "LMS Student"}],
    })
    user.insert(ignore_permissions=True)
    print(f"  [created] User {email}")
    return email


def _ensure_membership(email, plan, membership_type, credit_balance):
    """Create CEU Membership if one doesn't already exist for the user."""
    existing = frappe.db.exists("CEU Membership", {"member": email})
    if existing:
        print(f"  [skip] CEU Membership for {email} already exists ({existing})")
        return existing

    start = today()
    end = add_years(start, 1)

    membership = frappe.get_doc({
        "doctype": "CEU Membership",
        "member": email,
        "plan": plan,
        "membership_type": membership_type,
        "status": "Active",
        "start_date": start,
        "end_date": end,
        "credit_balance": credit_balance,
    })
    membership.insert(ignore_permissions=True)
    print(f"  [created] CEU Membership for {email} ({membership_type}, balance={credit_balance})")

    if credit_balance > 0:
        _create_allocation_ledger(membership.name, email, credit_balance)

    return membership.name


def _create_allocation_ledger(membership_name, email, hours):
    """Create initial Allocation ledger entry."""
    ledger = frappe.get_doc({
        "doctype": "CEU Credit Ledger",
        "membership": membership_name,
        "user": email,
        "transaction_type": "Allocation",
        "hours": hours,
        "balance_after": hours,
        "timestamp": now_datetime(),
        "notes": "Seed allocation for QA testing",
    })
    ledger.insert(ignore_permissions=True)
    print(f"  [created] Ledger Allocation {hours}h for {email}")


def _ensure_company(company_name, admin_email, member_emails, membership_name):
    """Create Company Account if it doesn't exist."""
    if frappe.db.exists("Company Account", company_name):
        print(f"  [skip] Company Account '{company_name}' already exists")
        return

    today_date = today()

    admins = [{"user": admin_email, "added_on": today_date}]

    members = [
        {
            "user": email,
            "status": "Active",
            "invited_on": today_date,
            "joined_on": today_date,
        }
        for email in member_emails
    ]

    company = frappe.get_doc({
        "doctype": "Company Account",
        "company_name": company_name,
        "status": "Active",
        "billing_email": admin_email,
        "max_seats": 10,
        "membership": membership_name,
        "admins": admins,
        "members": members,
    })
    company.insert(ignore_permissions=True)
    print(f"  [created] Company Account '{company_name}'")


def seed():
    frappe.flags.ignore_permissions = True

    print("\n=== Seeding test users ===\n")

    print("→ PPT Employee Plan")
    _ensure_ppt_employee_plan()

    membership_map = {}

    for persona in USERS:
        email = persona["email"]
        print(f"→ {email}")
        _ensure_user(email, persona["first_name"], persona["last_name"])

        m = persona["membership"]
        if m:
            membership_name = _ensure_membership(
                email,
                m["plan"],
                m["membership_type"],
                m["credit_balance"],
            )
            membership_map[email] = membership_name

    print(f"\n→ Company: {COMPANY['company_name']}")
    company_membership = membership_map.get(COMPANY["admin_email"])
    _ensure_company(
        COMPANY["company_name"],
        COMPANY["admin_email"],
        COMPANY["member_emails"],
        company_membership,
    )

    frappe.db.commit()
    print("\n=== Done. All test data committed. ===\n")

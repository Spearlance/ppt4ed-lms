import json

import frappe
from frappe import _
from frappe.utils import now_datetime


@frappe.whitelist()
def get_member_admin_details(user: str):
    """Get full admin view of a member's membership, company, and enrollments."""
    frappe.only_for(["Moderator", "System Manager"])

    from lms.lms.ceu_user_type import get_user_type

    user_type_data = get_user_type(user)

    membership_data = None
    memberships = frappe.get_all(
        "CEU Membership",
        filters={"member": user},
        fields=[
            "name",
            "plan",
            "membership_type",
            "status",
            "start_date",
            "end_date",
            "credit_balance",
            "stripe_subscription_id",
            "stripe_customer_id",
        ],
        order_by="creation desc",
        limit=1,
    )
    if memberships:
        membership_data = memberships[0]

    company_data = None
    company_member = frappe.db.get_value(
        "Company Member",
        {"user": user, "parenttype": "Company Account"},
        ["parent", "status"],
        as_dict=True,
    )
    if company_member:
        company = frappe.get_doc("Company Account", company_member.parent)
        is_admin = any(a.user == user for a in company.admins)
        company_data = {
            "name": company.name,
            "company_name": company.company_name,
            "status": company.status,
            "role": "Admin" if is_admin else "Member",
            "member_status": company_member.status,
        }

    enrollments = frappe.get_all(
        "LMS Enrollment",
        filters={"member": user},
        fields=["name", "course", "creation", "credit_source", "membership"],
        order_by="creation desc",
        limit=50,
    )
    for e in enrollments:
        e["course_title"] = frappe.db.get_value("LMS Course", e.course, "title") or e.course

    return {
        "user": user,
        "user_type": user_type_data["type"],
        "membership": membership_data,
        "company": company_data,
        "enrollments": enrollments,
    }


@frappe.whitelist()
def admin_adjust_credits(membership: str, hours: float, reason: str):
    """Manually adjust credits on a membership (admin action)."""
    frappe.only_for(["Moderator", "System Manager"])

    doc = frappe.get_doc("CEU Membership", membership)
    doc.credit_balance += hours
    if doc.credit_balance < 0:
        frappe.throw(_("Cannot reduce credits below zero"))
    doc.save(ignore_permissions=True)

    frappe.get_doc(
        {
            "doctype": "CEU Credit Ledger",
            "membership": membership,
            "user": frappe.session.user,
            "transaction_type": "Admin Adjustment",
            "hours": hours,
            "balance_after": doc.credit_balance,
            "course": reason,
            "timestamp": now_datetime(),
        }
    ).insert(ignore_permissions=True)

    return {"credit_balance": doc.credit_balance}


@frappe.whitelist()
def admin_cancel_subscription(membership: str):
    """Cancel a Stripe subscription and update membership status."""
    frappe.only_for(["Moderator", "System Manager"])

    doc = frappe.get_doc("CEU Membership", membership)
    if not doc.stripe_subscription_id:
        frappe.throw(_("No Stripe subscription linked"))

    from lms.lms.ceu_stripe import get_stripe

    s = get_stripe()
    s.Subscription.cancel(doc.stripe_subscription_id)

    doc.status = "Cancelled"
    doc.save(ignore_permissions=True)

    company_name = frappe.db.get_value(
        "Company Account", {"membership": membership}, "name"
    )
    if company_name:
        frappe.db.set_value("Company Account", company_name, "status", "Suspended")

    return {"status": "cancelled"}


@frappe.whitelist()
def admin_change_plan(membership: str, new_plan: str):
    """Change a membership's plan (swaps Stripe subscription)."""
    frappe.only_for(["Moderator", "System Manager"])

    doc = frappe.get_doc("CEU Membership", membership)
    plan_doc = frappe.get_doc("CEU Membership Plan", new_plan)

    if doc.stripe_subscription_id and plan_doc.stripe_price_id:
        from lms.lms.ceu_stripe import get_stripe

        s = get_stripe()
        subscription = s.Subscription.retrieve(doc.stripe_subscription_id)
        s.Subscription.modify(
            doc.stripe_subscription_id,
            items=[
                {
                    "id": subscription["items"]["data"][0]["id"],
                    "price": plan_doc.stripe_price_id,
                }
            ],
            proration_behavior="create_prorations",
        )

    doc.plan = new_plan
    doc.membership_type = plan_doc.plan_type
    doc.save(ignore_permissions=True)

    return {"plan": new_plan, "membership_type": plan_doc.plan_type}


@frappe.whitelist()
def get_company_admin_details(company: str):
    """Get full admin view of a company."""
    frappe.only_for(["Moderator", "System Manager"])

    doc = frappe.get_doc("Company Account", company)

    members = []
    for m in doc.members:
        user = frappe.db.get_value(
            "User",
            m.user,
            ["full_name", "email", "last_active", "user_image"],
            as_dict=True,
        )
        enrollment_count = frappe.db.count("LMS Enrollment", {"member": m.user})
        members.append(
            {
                "user": m.user,
                "full_name": user.full_name if user else m.user,
                "email": user.email if user else m.user,
                "user_image": user.user_image if user else None,
                "status": m.status,
                "invited_on": m.invited_on,
                "joined_on": m.joined_on,
                "enrollment_count": enrollment_count,
                "last_active": user.last_active if user else None,
            }
        )

    admins = []
    for a in doc.admins:
        user = frappe.db.get_value("User", a.user, ["full_name", "email"], as_dict=True)
        admins.append(
            {
                "user": a.user,
                "full_name": user.full_name if user else a.user,
                "email": user.email if user else a.user,
                "added_on": a.added_on,
            }
        )

    membership_data = None
    if doc.membership:
        membership_data = frappe.db.get_value(
            "CEU Membership",
            doc.membership,
            [
                "name",
                "plan",
                "membership_type",
                "status",
                "start_date",
                "end_date",
                "credit_balance",
                "stripe_subscription_id",
                "stripe_customer_id",
            ],
            as_dict=True,
        )

    return {
        "name": doc.name,
        "company_name": doc.company_name,
        "status": doc.status,
        "billing_email": doc.billing_email,
        "max_seats": doc.max_seats,
        "membership": membership_data,
        "members": members,
        "admins": admins,
    }


@frappe.whitelist()
def admin_update_company(company: str, fields: "dict | str"):
    """Update company details (admin action)."""
    frappe.only_for(["Moderator", "System Manager"])

    if isinstance(fields, str):
        fields = json.loads(fields)

    allowed = {"billing_email", "max_seats", "status"}
    doc = frappe.get_doc("Company Account", company)

    for key, value in fields.items():
        if key in allowed:
            setattr(doc, key, value)

    doc.save(ignore_permissions=True)
    return {"status": "updated"}


@frappe.whitelist()
def admin_remove_member_from_company(user: str, company: str):
    """Remove a member from a company (sets status to Removed)."""
    frappe.only_for(["Moderator", "System Manager"])

    doc = frappe.get_doc("Company Account", company)
    for m in doc.members:
        if m.user == user:
            m.status = "Removed"
    doc.save(ignore_permissions=True)
    return {"status": "removed"}


@frappe.whitelist()
def admin_promote_to_company_admin(user: str, company: str):
    """Promote a company member to admin."""
    frappe.only_for(["Moderator", "System Manager"])

    doc = frappe.get_doc("Company Account", company)

    existing = [a for a in doc.admins if a.user == user]
    if existing:
        frappe.throw(_("User is already a company admin"))

    doc.append("admins", {"user": user})
    doc.save(ignore_permissions=True)
    return {"status": "promoted"}


@frappe.whitelist()
def get_company_credit_history(company: str):
    """Get credit ledger for a company's membership (admin view)."""
    frappe.only_for(["Moderator", "System Manager"])

    membership_name = frappe.db.get_value("Company Account", company, "membership")
    if not membership_name:
        return []

    entries = frappe.get_all(
        "CEU Credit Ledger",
        filters={"membership": membership_name},
        fields=[
            "name",
            "user",
            "transaction_type",
            "hours",
            "balance_after",
            "course",
            "timestamp",
        ],
        order_by="timestamp desc",
        limit=100,
    )

    for entry in entries:
        entry["user_name"] = (
            frappe.db.get_value("User", entry.user, "full_name") or entry.user
        )

    return entries

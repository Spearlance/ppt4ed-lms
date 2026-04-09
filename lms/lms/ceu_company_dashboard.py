import frappe
from frappe import _
from frappe.utils import now_datetime


def _get_user_company():
    """Get the Company Account where the current user is an admin."""
    companies = frappe.get_all(
        "Company Admin",
        filters={"user": frappe.session.user, "parenttype": "Company Account"},
        fields=["parent"],
        limit=1
    )
    if not companies:
        frappe.throw(_("You are not a company admin"), frappe.PermissionError)
    return companies[0].parent


@frappe.whitelist()
def get_company_dashboard():
    """Get company overview data for the logged-in company admin."""
    company_name = _get_user_company()
    company = frappe.get_doc("Company Account", company_name)

    membership_data = None
    if company.membership:
        membership = frappe.get_doc("CEU Membership", company.membership)
        membership_data = {
            "name": membership.name,
            "plan": membership.plan,
            "status": membership.status,
            "credit_balance": membership.credit_balance,
            "stripe_customer_id": membership.stripe_customer_id,
        }

    return {
        "company_name": company.company_name,
        "member_count": len(company.members),
        "admin_count": len(company.admins),
        "membership": membership_data,
    }


@frappe.whitelist()
def get_company_members():
    """Get list of company members (employees)."""
    company_name = _get_user_company()
    company = frappe.get_doc("Company Account", company_name)

    members = []
    for m in company.members:
        user = frappe.db.get_value(
            "User", m.user, ["full_name", "email", "last_active"], as_dict=True
        )
        enrollment_count = frappe.db.count(
            "LMS Enrollment", {"member": m.user}
        )
        members.append({
            "user": m.user,
            "full_name": user.full_name if user else m.user,
            "email": user.email if user else m.user,
            "last_active": user.last_active if user else None,
            "enrollment_count": enrollment_count,
        })

    return members


@frappe.whitelist()
def get_company_invites():
    """Get pending and recent invites for the company."""
    company_name = _get_user_company()

    invites = frappe.get_all(
        "Company Invite",
        filters={"company": company_name},
        fields=["name", "email", "status", "creation", "token"],
        order_by="creation desc",
        limit=50
    )

    return invites


@frappe.whitelist()
def send_company_invite(email):
    """Send an invite to join the company."""
    company_name = _get_user_company()

    existing = frappe.db.exists(
        "Company Invite",
        {"company": company_name, "email": email, "status": "Pending"}
    )
    if existing:
        frappe.throw(_("An invite is already pending for this email"))

    invite = frappe.get_doc({
        "doctype": "Company Invite",
        "company": company_name,
        "email": email,
        "status": "Pending",
    }).insert(ignore_permissions=True)

    frappe.sendmail(
        recipients=[email],
        subject=f"You're invited to join {company_name} on PPT4ed",
        message=f"You have been invited to join {company_name}. "
                f"Use invite code: {invite.token}"
    )

    return {"invite": invite.name, "status": "sent"}


@frappe.whitelist()
def revoke_company_invite(invite_name):
    """Revoke a pending company invite."""
    _get_user_company()

    invite = frappe.get_doc("Company Invite", invite_name)
    if invite.status != "Pending":
        frappe.throw(_("Only pending invites can be revoked"))

    invite.status = "Revoked"
    invite.save(ignore_permissions=True)

    return {"status": "revoked"}


@frappe.whitelist()
def get_credit_history():
    """Get credit ledger entries for the company's membership."""
    company_name = _get_user_company()
    company = frappe.get_doc("Company Account", company_name)

    if not company.membership:
        return []

    entries = frappe.get_all(
        "CEU Credit Ledger",
        filters={"membership": company.membership},
        fields=[
            "name", "user", "transaction_type", "hours",
            "balance_after", "course", "timestamp"
        ],
        order_by="timestamp desc",
        limit=100
    )

    for entry in entries:
        entry["user_name"] = frappe.db.get_value(
            "User", entry.user, "full_name"
        ) or entry.user

    return entries


@frappe.whitelist()
def get_enrollment_requests():
    """Get enrollment requests for the company."""
    company_name = _get_user_company()

    requests = frappe.get_all(
        "CEU Enrollment Request",
        filters={"company": company_name},
        fields=[
            "name", "user", "course", "status",
            "creation", "reviewed_by", "reviewed_on"
        ],
        order_by="creation desc",
        limit=50
    )

    for req in requests:
        req["user_name"] = frappe.db.get_value(
            "User", req.user, "full_name"
        ) or req.user
        req["course_title"] = frappe.db.get_value(
            "LMS Course", req.course, "title"
        ) or req.course

    return requests

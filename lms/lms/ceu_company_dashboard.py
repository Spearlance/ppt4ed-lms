import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, now_datetime, nowdate


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


def _get_member_company():
    """Get the Company Account where the current user is an active member."""
    member = frappe.db.get_value(
        "Company Member",
        {"user": frappe.session.user, "status": "Active", "parenttype": "Company Account"},
        "parent"
    )
    if not member:
        frappe.throw(_("You are not a company member"), frappe.PermissionError)
    return member


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

    active_members = [m.user for m in company.members if m.user and m.status != "Removed"]
    active_enrollments = 0
    completed_enrollments = 0
    if active_members:
        rows = frappe.get_all(
            "LMS Enrollment",
            filters={"member": ["in", active_members]},
            fields=["progress"],
        )
        for r in rows:
            if (r.progress or 0) >= 100:
                completed_enrollments += 1
            else:
                active_enrollments += 1

    return {
        "company_name": company.company_name,
        "member_count": len(active_members),
        "admin_count": len(company.admins),
        "active_enrollments": active_enrollments,
        "completed_enrollments": completed_enrollments,
        "membership": membership_data,
    }


@frappe.whitelist()
def get_company_members():
    """Get list of active company members (employees). Removed members
    are hidden — keep them in the underlying child table for audit but
    don't surface in the admin UI."""
    company_name = _get_user_company()
    company = frappe.get_doc("Company Account", company_name)

    members = []
    for m in company.members:
        if m.status == "Removed":
            continue
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
def remove_company_member(user: str):
    """Company-admin endpoint: remove an employee from the caller's company.
    Triggers the personal-signup email so the user knows their account
    persists outside the company."""
    from lms.lms.ceu_admin import remove_member_and_notify

    company_name = _get_user_company()

    if user == frappe.session.user:
        frappe.throw(_("You cannot remove yourself from the company"))

    return remove_member_and_notify(user, company_name)


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


@frappe.whitelist()
def get_team_activity(period_days: int = 30, top_courses_limit: int = 5):
	"""Aggregate per-employee learning activity for the company admin's team.

	Returns lifetime + period-bound enrollment, completion, and CEU consumption
	per member, plus the most-enrolled courses across the team. ``period_days``
	bounds the period-relative metrics (default last 30 days).
	"""
	company_name = _get_user_company()
	company = frappe.get_doc("Company Account", company_name)
	period_days = max(cint(period_days) or 30, 1)
	top_courses_limit = max(cint(top_courses_limit) or 5, 1)
	period_start = add_days(nowdate(), -period_days)

	member_users = [m.user for m in company.members if m.user]
	if not member_users:
		return {
			"period_days": period_days,
			"members": [],
			"totals": _empty_totals(period_days),
			"top_courses": [],
		}

	enrollments = frappe.get_all(
		"LMS Enrollment",
		filters={"member": ["in", member_users]},
		fields=["member", "course", "progress", "modified", "creation"],
	)
	certs = frappe.get_all(
		"LMS Certificate",
		filters={"member": ["in", member_users]},
		fields=["member", "course", "creation", "ceu_hours"],
	)
	user_meta = {
		row.name: row
		for row in frappe.get_all(
			"User",
			filters={"name": ["in", member_users]},
			fields=["name", "full_name", "email", "last_active"],
		)
	}

	ceu_by_user = {}
	if company.membership:
		ceu_rows = frappe.get_all(
			"CEU Credit Ledger",
			filters={
				"membership": company.membership,
				"user": ["in", member_users],
				"timestamp": [">=", period_start],
				"transaction_type": ["in", ["Enrollment", "Direct Purchase"]],
			},
			fields=["user", "SUM(hours) as total_hours"],
			group_by="user",
		)
		ceu_by_user = {r.user: flt(r.total_hours) for r in ceu_rows}

	in_progress_by_user = {}
	completed_total_by_user = {}
	for e in enrollments:
		if (e.progress or 0) >= 100:
			completed_total_by_user[e.member] = completed_total_by_user.get(e.member, 0) + 1
		else:
			in_progress_by_user[e.member] = in_progress_by_user.get(e.member, 0) + 1

	completed_period_by_user = {}
	for c in certs:
		if str(c.creation) >= period_start:
			completed_period_by_user[c.member] = completed_period_by_user.get(c.member, 0) + 1

	members_payload = []
	for user in member_users:
		meta = user_meta.get(user)
		members_payload.append(
			{
				"user": user,
				"full_name": (meta.full_name if meta else user) or user,
				"email": (meta.email if meta else user) or user,
				"last_active": meta.last_active if meta else None,
				"in_progress": in_progress_by_user.get(user, 0),
				"completed_total": completed_total_by_user.get(user, 0),
				"completed_period": completed_period_by_user.get(user, 0),
				"ceu_debited_period": ceu_by_user.get(user, 0.0),
			}
		)
	members_payload.sort(
		key=lambda m: (m["completed_period"], m["ceu_debited_period"]),
		reverse=True,
	)

	totals = {
		"members": len(member_users),
		"active_learners_period": sum(
			1
			for m in members_payload
			if m["completed_period"] or m["ceu_debited_period"]
		),
		"completed_total": sum(completed_total_by_user.values()),
		"completed_period": sum(completed_period_by_user.values()),
		"ceu_debited_period": sum(ceu_by_user.values()),
		"avg_ceu_per_member_period": (
			sum(ceu_by_user.values()) / len(member_users) if member_users else 0
		),
	}

	enrollment_counts = {}
	completion_counts = {}
	for e in enrollments:
		enrollment_counts[e.course] = enrollment_counts.get(e.course, 0) + 1
		if (e.progress or 0) >= 100:
			completion_counts[e.course] = completion_counts.get(e.course, 0) + 1

	top_course_names = sorted(
		enrollment_counts.keys(),
		key=lambda c: (enrollment_counts[c], completion_counts.get(c, 0)),
		reverse=True,
	)[:top_courses_limit]

	titles = (
		dict(
			frappe.get_all(
				"LMS Course",
				filters={"name": ["in", top_course_names]},
				fields=["name", "title"],
				as_list=True,
			)
		)
		if top_course_names
		else {}
	)
	top_courses_payload = [
		{
			"course": c,
			"title": titles.get(c, c),
			"enrollment_count": enrollment_counts[c],
			"completed_count": completion_counts.get(c, 0),
		}
		for c in top_course_names
	]

	return {
		"period_days": period_days,
		"members": members_payload,
		"totals": totals,
		"top_courses": top_courses_payload,
	}


def _empty_totals(period_days: int):
	return {
		"members": 0,
		"active_learners_period": 0,
		"completed_total": 0,
		"completed_period": 0,
		"ceu_debited_period": 0,
		"avg_ceu_per_member_period": 0,
	}


@frappe.whitelist()
def get_my_company_credits():
    """Get credit info for the current user as a company member."""
    company_name = _get_member_company()
    company = frappe.get_doc("Company Account", company_name)

    if not company.membership:
        return {
            "company_name": company.company_name,
            "credit_balance": 0,
            "membership_status": None,
            "my_transactions": [],
        }

    membership = frappe.get_doc("CEU Membership", company.membership)

    entries = frappe.get_all(
        "CEU Credit Ledger",
        filters={
            "membership": company.membership,
            "user": frappe.session.user,
        },
        fields=[
            "name", "transaction_type", "hours",
            "balance_after", "course", "timestamp"
        ],
        order_by="timestamp desc",
        limit=50
    )

    for entry in entries:
        entry["course_title"] = frappe.db.get_value(
            "LMS Course", entry.course, "title"
        ) if entry.course else None

    return {
        "company_name": company.company_name,
        "credit_balance": membership.credit_balance,
        "membership_status": membership.status,
        "my_transactions": entries,
    }

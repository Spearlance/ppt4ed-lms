import frappe
from frappe.utils import add_days, add_months, cint, flt, getdate, nowdate


def _require_admin():
    """Ensure only LMS admins (System Manager or Global Admin) can access reports."""
    frappe.only_for(["System Manager", "Global Admin"])


def _date_window(from_date=None, to_date=None):
    """Default to the last 12 full months plus the current one."""
    to_date = getdate(to_date or nowdate())
    from_date = getdate(from_date or add_months(nowdate(), -12))
    if from_date > to_date:
        from_date, to_date = to_date, from_date
    return from_date, to_date


@frappe.whitelist()
def get_money_summary(from_date=None, to_date=None):
    """Dollars in for a date range, with the previous equal-length range for context.

    Reads `CEU Transaction`, which mirrors Stripe. Amounts are what Stripe
    charged: gross, refunds and gross minus refunds. Stripe processing fees are
    not included because they are not stored per transaction.
    """
    _require_admin()
    from_date, to_date = _date_window(from_date, to_date)

    span_days = (to_date - from_date).days + 1
    prev_to = add_days(from_date, -1)
    prev_from = add_days(prev_to, -(span_days - 1))

    def totals(start, end):
        row = frappe.db.sql("""
            SELECT
                COUNT(*) AS transactions,
                COALESCE(SUM(gross_amount), 0) AS gross,
                COALESCE(SUM(refunded_amount), 0) AS refunded,
                COALESCE(SUM(net_amount), 0) AS net,
                COUNT(DISTINCT member) AS buyers
            FROM `tabCEU Transaction`
            WHERE DATE(transaction_date) BETWEEN %(start)s AND %(end)s
              AND status != 'Failed'
        """, {"start": start, "end": end}, as_dict=True)
        return row[0] if row else {}

    current = totals(from_date, to_date)
    previous = totals(prev_from, prev_to)

    by_type = frappe.db.sql("""
        SELECT
            transaction_type,
            COUNT(*) AS transactions,
            COALESCE(SUM(gross_amount), 0) AS gross,
            COALESCE(SUM(refunded_amount), 0) AS refunded,
            COALESCE(SUM(net_amount), 0) AS net
        FROM `tabCEU Transaction`
        WHERE DATE(transaction_date) BETWEEN %(start)s AND %(end)s
          AND status != 'Failed'
        GROUP BY transaction_type
        ORDER BY net DESC
    """, {"start": from_date, "end": to_date}, as_dict=True)

    by_month = frappe.db.sql("""
        SELECT
            DATE_FORMAT(transaction_date, '%%Y-%%m') AS period,
            COUNT(*) AS transactions,
            COALESCE(SUM(gross_amount), 0) AS gross,
            COALESCE(SUM(refunded_amount), 0) AS refunded,
            COALESCE(SUM(net_amount), 0) AS net
        FROM `tabCEU Transaction`
        WHERE DATE(transaction_date) BETWEEN %(start)s AND %(end)s
          AND status != 'Failed'
        GROUP BY period
        ORDER BY period DESC
    """, {"start": from_date, "end": to_date}, as_dict=True)

    top_items = frappe.db.sql("""
        SELECT
            COALESCE(item_title, description, 'Unlabelled') AS item_title,
            transaction_type,
            COUNT(*) AS transactions,
            COALESCE(SUM(net_amount), 0) AS net
        FROM `tabCEU Transaction`
        WHERE DATE(transaction_date) BETWEEN %(start)s AND %(end)s
          AND status != 'Failed'
        GROUP BY item_title, transaction_type
        ORDER BY net DESC
        LIMIT 10
    """, {"start": from_date, "end": to_date}, as_dict=True)

    def change_pct(now_value, then_value):
        now_value, then_value = flt(now_value), flt(then_value)
        if not then_value:
            return None
        return round((now_value - then_value) / then_value * 100, 1)

    return {
        "from_date": str(from_date),
        "to_date": str(to_date),
        "previous_from_date": str(prev_from),
        "previous_to_date": str(prev_to),
        "totals": current,
        "previous_totals": previous,
        "change": {
            "net_pct": change_pct(current.get("net"), previous.get("net")),
            "transactions_pct": change_pct(current.get("transactions"), previous.get("transactions")),
        },
        "by_type": by_type,
        "by_month": by_month,
        "top_items": top_items,
        "fee_note": "Amounts are Stripe charges. Refunds are subtracted in Net. Stripe processing fees are not included.",
    }


@frappe.whitelist()
def get_transactions_report(
    from_date=None, to_date=None, transaction_type=None, search=None, limit=200, start=0
):
    """Individual Stripe transactions with the member and what they bought."""
    _require_admin()
    from_date, to_date = _date_window(from_date, to_date)

    conditions = ["DATE(t.transaction_date) BETWEEN %(start_date)s AND %(end_date)s"]
    params = {
        "start_date": from_date,
        "end_date": to_date,
        "limit": min(cint(limit) or 200, 2000),
        "offset": cint(start) or 0,
    }

    if transaction_type and transaction_type != "All":
        conditions.append("t.transaction_type = %(transaction_type)s")
        params["transaction_type"] = transaction_type

    if search:
        conditions.append("""(
            t.customer_email LIKE %(search)s
            OR t.member_full_name LIKE %(search)s
            OR t.item_title LIKE %(search)s
            OR t.description LIKE %(search)s
        )""")
        params["search"] = f"%{search}%"

    where = " AND ".join(conditions)

    rows = frappe.db.sql(f"""
        SELECT
            t.name AS stripe_id,
            t.transaction_date,
            t.transaction_type,
            t.status,
            t.gross_amount,
            t.refunded_amount,
            t.net_amount,
            t.currency,
            t.customer_email,
            t.member,
            COALESCE(t.member_full_name, u.full_name) AS member_full_name,
            t.item_type,
            t.item,
            COALESCE(t.item_title, t.description) AS item_title,
            t.stripe_invoice_id,
            t.stripe_subscription_id
        FROM `tabCEU Transaction` t
        LEFT JOIN `tabUser` u ON u.name = t.member
        WHERE {where}
        ORDER BY t.transaction_date DESC
        LIMIT %(limit)s OFFSET %(offset)s
    """, params, as_dict=True)

    total = frappe.db.sql(f"""
        SELECT COUNT(*) AS count, COALESCE(SUM(t.net_amount), 0) AS net
        FROM `tabCEU Transaction` t
        WHERE {where}
    """, params, as_dict=True)

    return {
        "rows": rows,
        "total_count": total[0].count if total else 0,
        "total_net": total[0].net if total else 0,
        "from_date": str(from_date),
        "to_date": str(to_date),
    }


@frappe.whitelist()
def get_member_purchase_detail(member):
    """Everything one person paid for and everything they are enrolled in.

    Saves the click-through the admin does today: contact record, then
    memberships, then enrollments.
    """
    _require_admin()

    user = frappe.db.get_value(
        "User", member, ["name", "full_name", "email"], as_dict=True
    )
    if not user:
        frappe.throw("Member not found")

    transactions = frappe.get_all(
        "CEU Transaction",
        filters={"member": user.name},
        fields=[
            "name as stripe_id", "transaction_date", "transaction_type", "status",
            "gross_amount", "refunded_amount", "net_amount", "currency", "item_title",
        ],
        order_by="transaction_date desc",
        limit=200,
    )

    enrollments = frappe.db.sql("""
        SELECT
            e.course,
            c.title AS course_title,
            e.progress,
            e.credit_source,
            e.creation AS enrolled_on
        FROM `tabLMS Enrollment` e
        LEFT JOIN `tabLMS Course` c ON c.name = e.course
        WHERE e.member = %(member)s
        ORDER BY e.creation DESC
    """, {"member": user.name}, as_dict=True)

    memberships = frappe.get_all(
        "CEU Membership",
        filters={"member": user.name},
        fields=["name", "plan", "membership_type", "status", "start_date", "end_date", "credit_balance"],
    )

    lifetime = frappe.db.sql("""
        SELECT COALESCE(SUM(net_amount), 0) AS net, COUNT(*) AS transactions
        FROM `tabCEU Transaction`
        WHERE member = %(member)s AND status != 'Failed'
    """, {"member": user.name}, as_dict=True)

    return {
        "member": user,
        "lifetime_net": lifetime[0].net if lifetime else 0,
        "lifetime_transactions": lifetime[0].transactions if lifetime else 0,
        "transactions": transactions,
        "enrollments": enrollments,
        "memberships": memberships,
    }


@frappe.whitelist()
def get_monthly_course_stats(from_date=None, to_date=None):
    """Per month, per course: enrollments, completions and CEU hours issued.

    `get_courses_taken_report` groups by course for all time, which cannot answer
    "how did last month go". This does.
    """
    _require_admin()
    from_date, to_date = _date_window(from_date, to_date)

    rows = frappe.db.sql("""
        SELECT
            DATE_FORMAT(e.creation, '%%Y-%%m') AS period,
            e.course,
            c.title AS course_title,
            COUNT(*) AS enrollments,
            SUM(CASE WHEN e.progress >= 100 THEN 1 ELSE 0 END) AS completions,
            COALESCE(SUM(CASE WHEN e.progress >= 100 THEN c.ceu_hours ELSE 0 END), 0) AS ceu_hours_issued
        FROM `tabLMS Enrollment` e
        JOIN `tabLMS Course` c ON c.name = e.course
        WHERE DATE(e.creation) BETWEEN %(start)s AND %(end)s
          AND (c.course_type IS NULL OR c.course_type != 'Resource')
        GROUP BY period, e.course
        ORDER BY period DESC, enrollments DESC
    """, {"start": from_date, "end": to_date}, as_dict=True)

    by_month = frappe.db.sql("""
        SELECT
            DATE_FORMAT(e.creation, '%%Y-%%m') AS period,
            COUNT(*) AS enrollments,
            COUNT(DISTINCT e.member) AS members,
            SUM(CASE WHEN e.progress >= 100 THEN 1 ELSE 0 END) AS completions,
            COALESCE(SUM(CASE WHEN e.progress >= 100 THEN c.ceu_hours ELSE 0 END), 0) AS ceu_hours_issued
        FROM `tabLMS Enrollment` e
        JOIN `tabLMS Course` c ON c.name = e.course
        WHERE DATE(e.creation) BETWEEN %(start)s AND %(end)s
          AND (c.course_type IS NULL OR c.course_type != 'Resource')
        GROUP BY period
        ORDER BY period DESC
    """, {"start": from_date, "end": to_date}, as_dict=True)

    return {
        "rows": rows,
        "by_month": by_month,
        "from_date": str(from_date),
        "to_date": str(to_date),
    }


@frappe.whitelist()
def get_credit_allocation_report(period="monthly"):
    """CEU credit allocations from the ledger, by period.

    This is what the old `get_revenue_report` actually measured: credit hours
    allocated, not money. Dollars now live in `get_money_summary`.
    """
    _require_admin()

    if period == "monthly":
        date_format = "%Y-%m"
    else:
        date_format = "%Y"

    entries = frappe.db.sql("""
        SELECT
            DATE_FORMAT(cl.timestamp, %(fmt)s) as period,
            COUNT(*) as transaction_count,
            SUM(cl.hours) as total_hours
        FROM `tabCEU Credit Ledger` cl
        WHERE cl.transaction_type = 'Allocation'
        GROUP BY DATE_FORMAT(cl.timestamp, %(fmt)s)
        ORDER BY period DESC
        LIMIT 24
    """, {"fmt": date_format}, as_dict=True)

    return entries


@frappe.whitelist()
def get_revenue_report(period="monthly"):
    """Deprecated alias for `get_credit_allocation_report`.

    Kept so a stale cached frontend bundle keeps working after deploy. Despite
    the name it never returned money.
    """
    return get_credit_allocation_report(period=period)


@frappe.whitelist()
def get_courses_taken_report():
    """Enrollments grouped by course and discipline. Excludes Resources (see get_resources_report)."""
    _require_admin()

    courses = frappe.db.sql("""
        SELECT
            e.course,
            c.title as course_title,
            COUNT(e.name) as enrollment_count,
            c.ceu_hours
        FROM `tabLMS Enrollment` e
        JOIN `tabLMS Course` c ON c.name = e.course
        WHERE e.course IS NOT NULL
          AND (c.course_type IS NULL OR c.course_type != 'Resource')
        GROUP BY e.course
        ORDER BY enrollment_count DESC
    """, as_dict=True)

    for course in courses:
        disciplines = frappe.get_all(
            "CEU Discipline Link",
            filters={"parent": course.course, "parenttype": "LMS Course"},
            fields=["discipline"],
        )
        course["disciplines"] = ", ".join(d.discipline for d in disciplines)

    return courses


@frappe.whitelist()
def get_resources_report():
    """Claims grouped by resource (LMS Course with course_type='Resource')."""
    _require_admin()

    resources = frappe.db.sql("""
        SELECT
            c.name as resource,
            c.title as resource_title,
            c.resource_type,
            c.audience,
            c.published,
            COUNT(DISTINCT e.member) as claim_count,
            MAX(e.creation) as last_claim_on
        FROM `tabLMS Course` c
        LEFT JOIN `tabLMS Enrollment` e ON e.course = c.name
        WHERE c.course_type = 'Resource'
        GROUP BY c.name
        ORDER BY claim_count DESC, c.title ASC
    """, as_dict=True)

    return resources


@frappe.whitelist()
def get_resource_claimers(resource: str):
    """Users who have claimed a given resource, most recent first."""
    _require_admin()

    if not frappe.db.exists("LMS Course", {"name": resource, "course_type": "Resource"}):
        frappe.throw("Resource not found")

    claimers = frappe.db.sql("""
        SELECT
            e.member,
            u.full_name as member_name,
            u.email as member_email,
            e.creation as claimed_on,
            e.progress
        FROM `tabLMS Enrollment` e
        LEFT JOIN `tabUser` u ON u.name = e.member
        WHERE e.course = %(resource)s
        ORDER BY e.creation DESC
    """, {"resource": resource}, as_dict=True)

    return claimers


@frappe.whitelist()
def get_members_report():
    """CEU memberships grouped by type and status."""
    _require_admin()

    members = frappe.db.sql("""
        SELECT
            m.membership_type,
            m.status,
            COUNT(*) as count,
            SUM(m.credit_balance) as total_credits
        FROM `tabCEU Membership` m
        GROUP BY m.membership_type, m.status
        ORDER BY m.membership_type, m.status
    """, as_dict=True)

    return members


@frappe.whitelist()
def get_member_usage_report():
    """Credit utilization per membership."""
    _require_admin()

    usage = frappe.db.sql("""
        SELECT
            m.name as membership,
            m.member,
            u.full_name as member_name,
            m.plan,
            m.credit_balance,
            m.status,
            COALESCE(allocated.total, 0) as total_allocated,
            COALESCE(used.total, 0) as total_used
        FROM `tabCEU Membership` m
        LEFT JOIN `tabUser` u ON u.name = m.member
        LEFT JOIN (
            SELECT membership, SUM(hours) as total
            FROM `tabCEU Credit Ledger`
            WHERE transaction_type = 'Allocation'
            GROUP BY membership
        ) allocated ON allocated.membership = m.name
        LEFT JOIN (
            SELECT membership, SUM(ABS(hours)) as total
            FROM `tabCEU Credit Ledger`
            WHERE transaction_type = 'Enrollment'
            GROUP BY membership
        ) used ON used.membership = m.name
        ORDER BY m.status, m.member
    """, as_dict=True)

    for row in usage:
        if row.total_allocated > 0:
            row["utilization_pct"] = round((row.total_used / row.total_allocated) * 100, 1)
        else:
            row["utilization_pct"] = 0

    return usage


@frappe.whitelist()
def get_credit_health_report():
    """Memberships with low balance or upcoming expiry.

    `CEU Membership` has no `expiry_date` column — the renewal date lives in
    `end_date`, which `handle_invoice_paid` pushes forward a year on every paid
    invoice. This query used to select `m.expiry_date`, so the whole Health tab
    failed with an unknown-column error. Aliased to `expiry_date` to keep the
    existing frontend column working.
    """
    _require_admin()

    three_months = add_months(nowdate(), 3)

    health = frappe.db.sql("""
        SELECT
            m.name as membership,
            m.member,
            u.full_name as member_name,
            m.plan,
            m.credit_balance,
            m.status,
            m.end_date as expiry_date
        FROM `tabCEU Membership` m
        LEFT JOIN `tabUser` u ON u.name = m.member
        WHERE m.status = 'Active'
          AND (m.credit_balance <= 2 OR m.end_date <= %(cutoff)s)
        ORDER BY m.credit_balance ASC
    """, {"cutoff": three_months}, as_dict=True)

    for row in health:
        flags = []
        if row.credit_balance <= 0:
            flags.append("Zero Balance")
        elif row.credit_balance <= 2:
            flags.append("Low Balance")
        if row.expiry_date and getdate(row.expiry_date) <= getdate(three_months):
            flags.append("Expiring Soon")
        row["flags"] = ", ".join(flags)

    return health


@frappe.whitelist()
def get_course_performance_report():
    """Completion rates per course."""
    _require_admin()

    courses = frappe.db.sql("""
        SELECT
            e.course,
            c.title as course_title,
            COUNT(*) as total_enrolled,
            SUM(CASE WHEN e.progress >= 100 THEN 1 ELSE 0 END) as completed,
            ROUND(
                SUM(CASE WHEN e.progress >= 100 THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
                1
            ) as completion_rate,
            ROUND(AVG(e.progress), 1) as avg_progress
        FROM `tabLMS Enrollment` e
        JOIN `tabLMS Course` c ON c.name = e.course
        WHERE e.course IS NOT NULL
        GROUP BY e.course
        ORDER BY total_enrolled DESC
    """, as_dict=True)

    return courses


@frappe.whitelist()
def get_discipline_demand_report():
    """Enrollment demand by CEU discipline."""
    _require_admin()

    demand = frappe.db.sql("""
        SELECT
            dl.discipline,
            COUNT(DISTINCT e.name) as enrollment_count,
            COUNT(DISTINCT e.course) as course_count,
            COUNT(DISTINCT e.member) as unique_members
        FROM `tabCEU Discipline Link` dl
        JOIN `tabLMS Course` c ON c.name = dl.parent AND dl.parenttype = 'LMS Course'
        JOIN `tabLMS Enrollment` e ON e.course = c.name
        GROUP BY dl.discipline
        ORDER BY enrollment_count DESC
    """, as_dict=True)

    return demand

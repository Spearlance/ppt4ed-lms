import frappe
from frappe.utils import add_months, getdate, nowdate


def _require_admin():
    """Ensure only LMS admins (System Manager or Global Admin) can access reports."""
    frappe.only_for(["System Manager", "Global Admin"])


@frappe.whitelist()
def get_revenue_report(period="monthly"):
    """Revenue from credit ledger allocations (Stripe payments)."""
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
    """Memberships with low balance or upcoming expiry."""
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
            m.expiry_date
        FROM `tabCEU Membership` m
        LEFT JOIN `tabUser` u ON u.name = m.member
        WHERE m.status = 'Active'
          AND (m.credit_balance <= 2 OR m.expiry_date <= %(cutoff)s)
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

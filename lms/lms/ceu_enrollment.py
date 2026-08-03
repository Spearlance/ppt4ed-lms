import frappe
from frappe import _
from frappe.utils import now_datetime


def send_enrollment_confirmation_email(
    member,
    course,
    credit_source,
    ceu_hours=0,
    amount=None,
    currency=None,
    payment_reference=None,
):
    """Email the learner a course enrollment confirmation (with receipt when paid).

    Best-effort: a mail failure must never roll back the enrollment or bubble
    a 5xx out of the Stripe webhook, so the whole body fails open.
    """
    try:
        from frappe.utils import fmt_money, format_date, get_url, today

        from lms.lms.utils import get_lms_route, lms_send_template_mail

        course_title = frappe.db.get_value("LMS Course", course, "title") or course
        first_name = frappe.db.get_value("User", member, "first_name") or member

        amount_display = None
        if amount:
            amount_display = fmt_money(amount, currency=(currency or "USD").upper())

        lms_send_template_mail(
            recipients=member,
            default_subject=_("Enrollment Confirmation for {0}").format(course_title),
            jinja_template="course_enrollment_confirmation",
            args={
                "first_name": first_name,
                "course_title": course_title,
                "credit_source": credit_source,
                "ceu_hours": ceu_hours,
                "amount_display": amount_display,
                "payment_reference": payment_reference,
                "purchase_date": format_date(today(), "long"),
                "course_url": get_url(get_lms_route(f"courses/{course}")),
            },
            template_name="Course Enrollment Confirmation",
            retry=3,
        )
    except Exception:
        frappe.log_error(
            title="Course enrollment confirmation email failed",
            message=f"member: {member}\ncourse: {course}\n\n{frappe.get_traceback()}",
        )


def check_enrollment_eligibility(membership_name, course_ceu_hours):
    """Check if a user can enroll based on their membership."""
    if not membership_name:
        return {"eligible": False, "reason": "No active membership"}

    membership = frappe.get_doc("CEU Membership", membership_name)

    if membership.status != "Active":
        return {"eligible": False, "reason": "Membership is not active"}

    if membership.credit_balance < course_ceu_hours:
        return {
            "eligible": False,
            "reason": f"Insufficient credits. Available: {membership.credit_balance}, Required: {course_ceu_hours}"
        }

    return {"eligible": True}


@frappe.whitelist()
def enroll_professional_member(course_name, membership_name):
    """Enroll a professional member using their credit pool."""
    course = frappe.get_doc("LMS Course", course_name)
    ceu_hours = frappe.db.get_value("LMS Course", course_name, "ceu_hours") or 0

    eligibility = check_enrollment_eligibility(membership_name, ceu_hours)
    if not eligibility["eligible"]:
        frappe.throw(_(eligibility["reason"]))

    from lms.lms.ceu_credits import debit_credits
    debit_credits(membership_name, frappe.session.user, ceu_hours, course=course_name)

    enrollment = frappe.get_doc({
        "doctype": "LMS Enrollment",
        "member": frappe.session.user,
        "course": course_name,
        "credit_source": "Professional Membership",
        "membership": membership_name,
    }).insert(ignore_permissions=True)

    send_enrollment_confirmation_email(
        member=frappe.session.user,
        course=course_name,
        credit_source="Professional Membership",
        ceu_hours=ceu_hours,
    )

    return enrollment.name


@frappe.whitelist()
def enroll_company_member(course_name, company_name):
    """Enroll a company employee - either directly or via approval request."""
    company = frappe.get_doc("Company Account", company_name)
    ceu_hours = frappe.db.get_value("LMS Course", course_name, "ceu_hours") or 0

    if not company.membership:
        frappe.throw(_("Company has no active membership"))

    membership = frappe.get_doc("CEU Membership", company.membership)

    if membership.require_enrollment_approval:
        request = frappe.get_doc({
            "doctype": "CEU Enrollment Request",
            "user": frappe.session.user,
            "course": course_name,
            "company": company_name,
            "status": "Pending"
        }).insert(ignore_permissions=True)

        for admin in company.admins:
            frappe.sendmail(
                recipients=[admin.user],
                subject=f"Enrollment Request: {course_name}",
                message=f"{frappe.session.user} is requesting enrollment in {course_name}."
            )

        return {"status": "pending_approval", "request": request.name}
    else:
        eligibility = check_enrollment_eligibility(company.membership, ceu_hours)
        if not eligibility["eligible"]:
            frappe.throw(_(eligibility["reason"]))

        from lms.lms.ceu_credits import debit_credits
        debit_credits(company.membership, frappe.session.user, ceu_hours, course=course_name)

        enrollment = frappe.get_doc({
            "doctype": "LMS Enrollment",
            "member": frappe.session.user,
            "course": course_name,
            "credit_source": "Company Membership",
            "membership": company.membership,
        }).insert(ignore_permissions=True)

        send_enrollment_confirmation_email(
            member=frappe.session.user,
            course=course_name,
            credit_source="Company Membership",
            ceu_hours=ceu_hours,
        )

        return {"status": "enrolled", "enrollment": enrollment.name}


@frappe.whitelist()
def approve_enrollment_request(request_name):
    """Company admin approves an enrollment request."""
    request = frappe.get_doc("CEU Enrollment Request", request_name)
    company = frappe.get_doc("Company Account", request.company)

    ceu_hours = frappe.db.get_value("LMS Course", request.course, "ceu_hours") or 0

    eligibility = check_enrollment_eligibility(company.membership, ceu_hours)
    if not eligibility["eligible"]:
        frappe.throw(_(eligibility["reason"]))

    from lms.lms.ceu_credits import debit_credits
    debit_credits(company.membership, request.user, ceu_hours, course=request.course)

    frappe.get_doc({
        "doctype": "LMS Enrollment",
        "member": request.user,
        "course": request.course,
        "credit_source": "Company Membership",
        "membership": company.membership,
    }).insert(ignore_permissions=True)

    send_enrollment_confirmation_email(
        member=request.user,
        course=request.course,
        credit_source="Company Membership",
        ceu_hours=ceu_hours,
    )

    request.status = "Approved"
    request.reviewed_by = frappe.session.user
    request.reviewed_on = now_datetime()
    request.save(ignore_permissions=True)

    return {"status": "approved"}


@frappe.whitelist()
def deny_enrollment_request(request_name):
    """Company admin denies an enrollment request."""
    request = frappe.get_doc("CEU Enrollment Request", request_name)
    request.status = "Denied"
    request.reviewed_by = frappe.session.user
    request.reviewed_on = now_datetime()
    request.save(ignore_permissions=True)

    return {"status": "denied"}


@frappe.whitelist()
def enroll_ppt_employee(course_name: str, membership_name: str):
    """Enroll a PPT Employee in a course immediately, free of charge.

    PPT staff are trusted internal users — they get instant enrollment with
    a zero-hour ledger entry (for audit) and no credit debit.
    """
    membership = frappe.get_doc("CEU Membership", membership_name)

    if membership.membership_type != "PPT Employee":
        frappe.throw(_("This function is only for PPT Employee memberships"))

    if membership.status != "Active":
        frappe.throw(_("Membership is not active"))

    if frappe.db.exists("LMS Enrollment", {"course": course_name, "member": frappe.session.user}):
        frappe.throw(_("Already enrolled in this course"))

    frappe.get_doc({
        "doctype": "CEU Credit Ledger",
        "membership": membership_name,
        "user": frappe.session.user,
        "course": course_name,
        "transaction_type": "Enrollment",
        "hours": 0,
        "balance_after": membership.credit_balance,
        "timestamp": now_datetime(),
        "notes": "PPT Employee — no charge",
    }).insert(ignore_permissions=True)

    enrollment = frappe.get_doc({
        "doctype": "LMS Enrollment",
        "member": frappe.session.user,
        "course": course_name,
        "credit_source": "PPT Employee",
        "membership": membership_name,
    }).insert(ignore_permissions=True)

    return {"status": "enrolled", "enrollment": enrollment.name}


@frappe.whitelist()
def register_ppt_employee_for_event(event_name: str, membership_name: str):
    """Register a PPT Employee for an event immediately, free of charge.

    Mirrors enroll_ppt_employee for courses. PPT staff bypass the Stripe
    paywall on paid events via the credit_source field on LMS Event
    Registration — LMSEventRegistration.validate_payment short-circuits
    when credit_source is set. Zero-hour ledger row is written for audit.
    """
    membership = frappe.get_doc("CEU Membership", membership_name)

    if membership.membership_type != "PPT Employee":
        frappe.throw(_("This function is only for PPT Employee memberships"))

    if membership.status != "Active":
        frappe.throw(_("Membership is not active"))

    if frappe.db.exists("LMS Event Registration", {"event": event_name, "member": frappe.session.user}):
        frappe.throw(_("Already registered for this event"))

    frappe.get_doc({
        "doctype": "CEU Credit Ledger",
        "membership": membership_name,
        "user": frappe.session.user,
        "event": event_name,
        "transaction_type": "Enrollment",
        "hours": 0,
        "balance_after": membership.credit_balance,
        "timestamp": now_datetime(),
        "notes": "PPT Employee — event no charge",
    }).insert(ignore_permissions=True)

    registration = frappe.get_doc({
        "doctype": "LMS Event Registration",
        "member": frappe.session.user,
        "event": event_name,
        "credit_source": "PPT Employee",
        "membership": membership_name,
    }).insert(ignore_permissions=True)

    return {"status": "registered", "registration": registration.name}

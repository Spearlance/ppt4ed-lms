import frappe
from frappe import _
from frappe.utils import now_datetime


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
    """Initiate PPT employee enrollment by sending a verification email.

    PPT employees get free courses, so we verify they still control their
    @ppt4kids.com inbox before each enrollment.
    """
    membership = frappe.get_doc("CEU Membership", membership_name)

    if membership.membership_type != "PPT Employee":
        frappe.throw(_("This function is only for PPT Employee memberships"))

    if membership.status != "Active":
        frappe.throw(_("Membership is not active"))

    if frappe.db.exists("LMS Enrollment", {"course": course_name, "member": frappe.session.user}):
        frappe.throw(_("Already enrolled in this course"))

    # Expire any existing pending verifications for this user + course
    for old in frappe.get_all(
        "PPT Enrollment Verification",
        filters={"user": frappe.session.user, "course": course_name, "status": "Pending"},
        pluck="name",
    ):
        frappe.db.set_value("PPT Enrollment Verification", old, "status", "Expired")

    verification = frappe.get_doc({
        "doctype": "PPT Enrollment Verification",
        "user": frappe.session.user,
        "course": course_name,
        "membership": membership_name,
        "status": "Pending",
    }).insert(ignore_permissions=True)

    course_title = frappe.db.get_value("LMS Course", course_name, "title") or course_name
    verify_url = frappe.utils.get_url(
        f"/api/method/lms.lms.ceu_enrollment.verify_ppt_enrollment?token={verification.token}"
    )

    frappe.sendmail(
        recipients=[frappe.session.user],
        subject=f"Confirm your enrollment in {course_title}",
        message=(
            f"<p>Click the link below to confirm your enrollment in <strong>{course_title}</strong>.</p>"
            f'<p><a href="{verify_url}">Confirm Enrollment</a></p>'
            f"<p>This link expires in 15 minutes.</p>"
        ),
    )

    return {"status": "verification_sent"}


@frappe.whitelist(allow_guest=True)
def verify_ppt_enrollment(token: str):
    """Verify a PPT enrollment token and complete the enrollment."""
    verification = frappe.db.get_value(
        "PPT Enrollment Verification",
        {"token": token},
        ["name", "user", "course", "membership", "status", "expires_on"],
        as_dict=True,
    )

    if not verification:
        frappe.throw(_("Invalid verification link"))

    if verification.status != "Pending":
        frappe.throw(_("This verification link has already been used"))

    if now_datetime() > verification.expires_on:
        frappe.db.set_value("PPT Enrollment Verification", verification.name, "status", "Expired")
        frappe.throw(_("This verification link has expired. Please try enrolling again."))

    membership = frappe.get_doc("CEU Membership", verification.membership)

    if membership.status != "Active":
        frappe.throw(_("Membership is no longer active"))

    if frappe.db.exists("LMS Enrollment", {"course": verification.course, "member": verification.user}):
        frappe.db.set_value("PPT Enrollment Verification", verification.name, "status", "Verified")
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = f"/lms/courses/{verification.course}"
        return

    # Write ledger entry (hours=0, no deduction)
    frappe.get_doc({
        "doctype": "CEU Credit Ledger",
        "membership": verification.membership,
        "user": verification.user,
        "course": verification.course,
        "transaction_type": "Enrollment",
        "hours": 0,
        "balance_after": membership.credit_balance,
        "timestamp": now_datetime(),
        "notes": "PPT Employee — no charge"
    }).insert(ignore_permissions=True)

    frappe.get_doc({
        "doctype": "LMS Enrollment",
        "member": verification.user,
        "course": verification.course,
        "credit_source": "PPT Employee",
        "membership": verification.membership,
    }).insert(ignore_permissions=True)

    frappe.db.set_value("PPT Enrollment Verification", verification.name, "status", "Verified")
    frappe.db.commit()

    frappe.local.response["type"] = "redirect"
    frappe.local.response["location"] = f"/lms/courses/{verification.course}"

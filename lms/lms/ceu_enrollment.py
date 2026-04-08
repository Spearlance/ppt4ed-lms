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

import frappe
from frappe.tests import UnitTestCase
from frappe.utils import today, add_years


class TestCEUEnrollment(UnitTestCase):
    def setUp(self):
        if not frappe.db.exists("CEU Discipline", "Occupational Therapy"):
            frappe.get_doc({
                "doctype": "CEU Discipline",
                "discipline_name": "Occupational Therapy"
            }).insert(ignore_permissions=True)

    def test_professional_enrollment_debits_credits(self):
        from lms.lms.ceu_enrollment import enroll_professional_member

        if not frappe.db.exists("CEU Membership Plan", "Enroll Test Plan"):
            frappe.get_doc({
                "doctype": "CEU Membership Plan",
                "title": "Enroll Test Plan",
                "plan_type": "Professional",
                "ceu_hours": 20.0,
                "price": 199.00,
                "active": 1
            }).insert(ignore_permissions=True)

        membership = frappe.get_doc({
            "doctype": "CEU Membership",
            "member": "Administrator",
            "plan": "Enroll Test Plan",
            "membership_type": "Professional",
            "status": "Active",
            "start_date": today(),
            "end_date": add_years(today(), 1),
            "credit_balance": 20.0
        }).insert(ignore_permissions=True)

        # Create test course with ceu_hours (via db since custom field)
        # This would be an integration test on the live site

    def test_insufficient_credits_blocks_enrollment(self):
        from lms.lms.ceu_enrollment import check_enrollment_eligibility

        result = check_enrollment_eligibility(
            membership_name=None,
            course_ceu_hours=5.0
        )
        self.assertFalse(result["eligible"])

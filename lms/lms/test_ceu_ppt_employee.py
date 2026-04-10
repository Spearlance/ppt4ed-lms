import frappe
from frappe.tests import UnitTestCase
from frappe.utils import today, add_years


class TestPPTEmployee(UnitTestCase):
    def test_can_create_ppt_employee_plan(self):
        if frappe.db.exists("CEU Membership Plan", "PPT Employee Test Plan"):
            frappe.delete_doc("CEU Membership Plan", "PPT Employee Test Plan", force=True, ignore_permissions=True)

        doc = frappe.get_doc({
            "doctype": "CEU Membership Plan",
            "title": "PPT Employee Test Plan",
            "plan_type": "PPT Employee",
            "ceu_hours": 0,
            "price": 0,
            "active": 1
        })
        doc.insert(ignore_permissions=True)
        self.assertEqual(doc.plan_type, "PPT Employee")
        self.assertEqual(doc.ceu_hours, 0)

    def test_can_create_ppt_employee_membership(self):
        if not frappe.db.exists("CEU Membership Plan", "PPT Employee Test Plan"):
            frappe.get_doc({
                "doctype": "CEU Membership Plan",
                "title": "PPT Employee Test Plan",
                "plan_type": "PPT Employee",
                "ceu_hours": 0,
                "price": 0,
                "active": 1
            }).insert(ignore_permissions=True)

        membership = frappe.get_doc({
            "doctype": "CEU Membership",
            "member": "Administrator",
            "plan": "PPT Employee Test Plan",
            "membership_type": "PPT Employee",
            "status": "Active",
            "start_date": today(),
            "end_date": add_years(today(), 1),
            "credit_balance": 0
        })
        membership.insert(ignore_permissions=True)
        self.assertEqual(membership.membership_type, "PPT Employee")

    def test_ppt_employee_enrollment_skips_balance_check(self):
        """PPT employees enroll without credit deduction but get a ledger entry."""
        from lms.lms.ceu_enrollment import enroll_ppt_employee

        if not frappe.db.exists("CEU Membership Plan", "PPT Employee Test Plan"):
            frappe.get_doc({
                "doctype": "CEU Membership Plan",
                "title": "PPT Employee Test Plan",
                "plan_type": "PPT Employee",
                "ceu_hours": 0,
                "price": 0,
                "active": 1
            }).insert(ignore_permissions=True)

        membership = frappe.get_doc({
            "doctype": "CEU Membership",
            "member": "Administrator",
            "plan": "PPT Employee Test Plan",
            "membership_type": "PPT Employee",
            "status": "Active",
            "start_date": today(),
            "end_date": add_years(today(), 1),
            "credit_balance": 0
        }).insert(ignore_permissions=True)

        # Need a course — use db.get_all to find one or create minimal
        courses = frappe.db.get_all("LMS Course", limit=1)
        if not courses:
            self.skipTest("No LMS Course exists for testing")

        course_name = courses[0].name

        result = enroll_ppt_employee(course_name, membership.name)

        # Should create enrollment
        self.assertTrue(frappe.db.exists("LMS Enrollment", {
            "member": "Administrator",
            "course": course_name,
            "credit_source": "PPT Employee"
        }))

        # Should create a ledger entry with hours=0
        ledger = frappe.get_last_doc("CEU Credit Ledger", filters={
            "membership": membership.name,
            "transaction_type": "Enrollment",
            "course": course_name
        })
        self.assertEqual(ledger.hours, 0)
        self.assertIn("PPT Employee", ledger.notes or "")

        # Balance should remain 0 (no deduction)
        membership.reload()
        self.assertEqual(membership.credit_balance, 0)

import frappe
from frappe.tests import UnitTestCase
from frappe.utils import today, add_years


class TestPPTEmployee(UnitTestCase):
    def test_can_create_ppt_employee_plan(self):
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

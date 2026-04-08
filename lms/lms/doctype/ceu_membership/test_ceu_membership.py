import frappe
from frappe.tests import UnitTestCase
from frappe.utils import today, add_years


class TestCEUMembership(UnitTestCase):
    def setUp(self):
        if not frappe.db.exists("CEU Membership Plan", "Test Pro 20"):
            frappe.get_doc({
                "doctype": "CEU Membership Plan",
                "title": "Test Pro 20",
                "plan_type": "Professional",
                "ceu_hours": 20.0,
                "price": 199.00,
                "active": 1
            }).insert(ignore_permissions=True)

    def test_create_membership(self):
        doc = frappe.get_doc({
            "doctype": "CEU Membership",
            "member": "Administrator",
            "plan": "Test Pro 20",
            "membership_type": "Professional",
            "status": "Active",
            "start_date": today(),
            "end_date": add_years(today(), 1),
            "credit_balance": 20.0
        })
        doc.insert(ignore_permissions=True)
        self.assertEqual(doc.credit_balance, 20.0)
        self.assertEqual(doc.status, "Active")

    def test_membership_status_options(self):
        doc = frappe.get_doc({
            "doctype": "CEU Membership",
            "member": "Administrator",
            "plan": "Test Pro 20",
            "membership_type": "Professional",
            "status": "Expired",
            "start_date": today(),
            "end_date": today(),
            "credit_balance": 0
        })
        doc.insert(ignore_permissions=True)
        self.assertEqual(doc.status, "Expired")

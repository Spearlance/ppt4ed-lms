import frappe
from frappe.tests import UnitTestCase


class TestCEUMembershipPlan(UnitTestCase):
    def test_create_professional_plan(self):
        doc = frappe.get_doc({
            "doctype": "CEU Membership Plan",
            "title": "Professional 20hr",
            "plan_type": "Professional",
            "ceu_hours": 20.0,
            "price": 199.00,
            "active": 1
        })
        doc.insert(ignore_permissions=True)
        self.assertEqual(doc.plan_type, "Professional")
        self.assertEqual(doc.ceu_hours, 20.0)

    def test_create_company_plan(self):
        doc = frappe.get_doc({
            "doctype": "CEU Membership Plan",
            "title": "Company 100hr",
            "plan_type": "Company",
            "ceu_hours": 100.0,
            "price": 899.00,
            "active": 1
        })
        doc.insert(ignore_permissions=True)
        self.assertEqual(doc.plan_type, "Company")

    def test_create_individual_business_plan(self):
        doc = frappe.get_doc({
            "doctype": "CEU Membership Plan",
            "title": "Individual Business 0hr",
            "plan_type": "Individual-Business",
            "ceu_hours": 0,
            "price": 500.00,
            "active": 1
        })
        doc.insert(ignore_permissions=True)
        self.assertEqual(doc.plan_type, "Individual-Business")
        self.assertEqual(doc.price, 500.00)

    def test_plan_type_required(self):
        doc = frappe.get_doc({
            "doctype": "CEU Membership Plan",
            "title": "No Type Plan",
            "ceu_hours": 10.0,
            "price": 99.00
        })
        with self.assertRaises(frappe.exceptions.MandatoryError):
            doc.insert(ignore_permissions=True)

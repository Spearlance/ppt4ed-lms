import frappe
from frappe.tests import UnitTestCase


class TestCompanyAccount(UnitTestCase):
    def test_create_company_account(self):
        doc = frappe.get_doc({
            "doctype": "Company Account",
            "company_name": "Test Therapy Group",
            "admins": [{"user": "Administrator"}]
        })
        doc.insert(ignore_permissions=True)
        self.assertEqual(doc.company_name, "Test Therapy Group")
        self.assertEqual(len(doc.admins), 1)

    def test_company_requires_name(self):
        doc = frappe.get_doc({
            "doctype": "Company Account",
            "admins": [{"user": "Administrator"}]
        })
        with self.assertRaises(frappe.exceptions.MandatoryError):
            doc.insert(ignore_permissions=True)

    def test_multiple_admins(self):
        doc = frappe.get_doc({
            "doctype": "Company Account",
            "company_name": "Multi Admin Corp",
            "admins": [
                {"user": "Administrator"},
                {"user": "Administrator"}
            ]
        })
        doc.insert(ignore_permissions=True)
        self.assertEqual(len(doc.admins), 2)

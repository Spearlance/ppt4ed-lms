import frappe
from frappe.tests import UnitTestCase
from frappe.utils import add_days, now_datetime


class TestCompanyInvite(UnitTestCase):
    def setUp(self):
        if not frappe.db.exists("Company Account", "Invite Test Corp"):
            frappe.get_doc({
                "doctype": "Company Account",
                "company_name": "Invite Test Corp",
                "admins": [{"user": "Administrator"}]
            }).insert(ignore_permissions=True)

    def test_create_invite(self):
        doc = frappe.get_doc({
            "doctype": "Company Invite",
            "company": "Invite Test Corp",
            "email": "employee@test.com",
            "status": "Pending",
            "expires_on": add_days(now_datetime(), 7)
        })
        doc.insert(ignore_permissions=True)
        self.assertTrue(doc.token)
        self.assertEqual(doc.status, "Pending")

    def test_token_auto_generated(self):
        doc = frappe.get_doc({
            "doctype": "Company Invite",
            "company": "Invite Test Corp",
            "email": "auto-token@test.com",
            "status": "Pending",
            "expires_on": add_days(now_datetime(), 7)
        })
        doc.insert(ignore_permissions=True)
        self.assertIsNotNone(doc.token)
        self.assertGreater(len(doc.token), 10)

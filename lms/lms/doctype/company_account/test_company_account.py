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

    def test_status_field_defaults_to_active(self):
        doc = frappe.get_doc({
            "doctype": "Company Account",
            "company_name": "Status Default Test Co",
            "admins": [{"user": "Administrator"}]
        })
        doc.insert(ignore_permissions=True)
        self.assertEqual(doc.status, "Active")

    def test_status_field_accepts_valid_values(self):
        for status in ("Active", "Suspended", "Cancelled"):
            doc = frappe.get_doc({
                "doctype": "Company Account",
                "company_name": f"Status Test {status}",
                "status": status,
                "admins": [{"user": "Administrator"}]
            })
            doc.insert(ignore_permissions=True)
            self.assertEqual(doc.status, status)

    def test_billing_email_field_accepts_email(self):
        doc = frappe.get_doc({
            "doctype": "Company Account",
            "company_name": "Billing Email Test Co",
            "billing_email": "billing@testco.com",
            "admins": [{"user": "Administrator"}]
        })
        doc.insert(ignore_permissions=True)
        self.assertEqual(doc.billing_email, "billing@testco.com")

    def test_max_seats_zero_means_unlimited(self):
        """max_seats=0 should allow any number of active members."""
        doc = frappe.get_doc({
            "doctype": "Company Account",
            "company_name": "Unlimited Seats Co",
            "max_seats": 0,
            "admins": [{"user": "Administrator"}],
            "members": [
                {"user": "Administrator", "status": "Active"},
            ]
        })
        # Should not raise
        doc.insert(ignore_permissions=True)

    def test_max_seats_enforced_when_exceeded(self):
        """Exceeding max_seats must raise ValidationError."""
        doc = frappe.get_doc({
            "doctype": "Company Account",
            "company_name": "Capped Seats Co",
            "max_seats": 1,
            "admins": [{"user": "Administrator"}],
            "members": [
                {"user": "user1@example.com", "status": "Active"},
                {"user": "user2@example.com", "status": "Active"},
            ]
        })
        with self.assertRaises(frappe.ValidationError):
            doc.insert(ignore_permissions=True)

    def test_max_seats_inactive_members_not_counted(self):
        """Inactive members should not count toward max_seats."""
        doc = frappe.get_doc({
            "doctype": "Company Account",
            "company_name": "Inactive Exclusion Co",
            "max_seats": 1,
            "admins": [{"user": "Administrator"}],
            "members": [
                {"user": "user1@example.com", "status": "Active"},
                {"user": "user2@example.com", "status": "Inactive"},
            ]
        })
        # Should not raise — only 1 active member against limit of 1
        doc.insert(ignore_permissions=True)

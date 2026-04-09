import frappe
from frappe.tests import IntegrationTestCase


class TestCompanyAccount(IntegrationTestCase):
    def tearDown(self):
        """Clean up test companies after each test."""
        for name in frappe.get_all(
            "Company Account",
            filters={"company_name": ["like", "Test_%"]},
            pluck="name"
        ):
            frappe.delete_doc("Company Account", name, force=True)
        frappe.db.commit()

    def test_create_company_account(self):
        doc = frappe.get_doc({
            "doctype": "Company Account",
            "company_name": "Test_Create_Co",
            "admins": [{"user": "Administrator"}]
        })
        doc.insert(ignore_permissions=True)
        self.assertEqual(doc.company_name, "Test_Create_Co")
        self.assertEqual(len(doc.admins), 1)

    def test_company_requires_name(self):
        doc = frappe.get_doc({
            "doctype": "Company Account",
            "admins": [{"user": "Administrator"}]
        })
        with self.assertRaises(frappe.exceptions.MandatoryError):
            doc.insert(ignore_permissions=True)

    def test_duplicate_admins_rejected(self):
        """Duplicate admin entries should raise ValidationError."""
        doc = frappe.get_doc({
            "doctype": "Company Account",
            "company_name": "Test_Dup_Admin_Co",
            "admins": [
                {"user": "Administrator"},
                {"user": "Administrator"}
            ]
        })
        with self.assertRaises(frappe.ValidationError):
            doc.insert(ignore_permissions=True)

    def test_status_field_defaults_to_active(self):
        doc = frappe.get_doc({
            "doctype": "Company Account",
            "company_name": "Test_Status_Default_Co",
        })
        doc.insert(ignore_permissions=True)
        self.assertEqual(doc.status, "Active")

    def test_status_field_accepts_valid_values(self):
        for i, status in enumerate(("Active", "Suspended", "Cancelled")):
            doc = frappe.get_doc({
                "doctype": "Company Account",
                "company_name": f"Test_Status_{i}_Co",
                "status": status,
            })
            doc.insert(ignore_permissions=True)
            self.assertEqual(doc.status, status)

    def test_billing_email_field_accepts_email(self):
        doc = frappe.get_doc({
            "doctype": "Company Account",
            "company_name": "Test_Billing_Email_Co",
            "billing_email": "billing@testco.com",
        })
        doc.insert(ignore_permissions=True)
        self.assertEqual(doc.billing_email, "billing@testco.com")

    def test_max_seats_zero_means_unlimited(self):
        """max_seats=0 should allow any number of active members."""
        doc = frappe.get_doc({
            "doctype": "Company Account",
            "company_name": "Test_Unlimited_Seats_Co",
            "max_seats": 0,
            "members": [
                {"user": "Administrator", "status": "Active"},
            ]
        })
        doc.insert(ignore_permissions=True)

    def test_max_seats_enforced_when_exceeded(self):
        """Exceeding max_seats must raise ValidationError."""
        doc = frappe.get_doc({
            "doctype": "Company Account",
            "company_name": "Test_Capped_Seats_Co",
            "max_seats": 1,
            "members": [
                {"user": "user1@example.com", "status": "Active"},
                {"user": "user2@example.com", "status": "Active"},
            ]
        })
        with self.assertRaises(frappe.ValidationError):
            doc.insert(ignore_permissions=True)

    def test_max_seats_removed_members_not_counted(self):
        """Removed members should not count toward max_seats."""
        doc = frappe.get_doc({
            "doctype": "Company Account",
            "company_name": "Test_Removed_Exclusion_Co",
            "max_seats": 1,
            "members": [
                {"user": "user1@example.com", "status": "Active"},
                {"user": "user2@example.com", "status": "Removed"},
            ]
        })
        # Should not raise — only 1 active member against limit of 1
        doc.insert(ignore_permissions=True)

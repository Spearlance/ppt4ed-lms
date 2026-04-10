import frappe
from frappe.tests import UnitTestCase
from unittest.mock import patch, MagicMock
from frappe.utils import today, add_years


class TestCEUStripeWebhooks(UnitTestCase):
    def test_handle_checkout_completed_one_off(self):
        from lms.lms.ceu_stripe_webhooks import handle_checkout_completed

        event_data = {
            "metadata": {
                "type": "one_off",
                "course": "test-course",
                "user": "Administrator"
            }
        }

        # Should create enrollment (test with mock if course doesn't exist)
        # Full integration test requires a real course - covered in Phase 5

    def test_handle_subscription_deleted_suspends_company(self):
        from lms.lms.ceu_stripe_webhooks import handle_subscription_deleted

        if not frappe.db.exists("CEU Membership Plan", "Company Webhook Test Plan"):
            frappe.get_doc({
                "doctype": "CEU Membership Plan",
                "title": "Company Webhook Test Plan",
                "plan_type": "Company",
                "ceu_hours": 40.0,
                "price": 499.00,
                "active": 1
            }).insert(ignore_permissions=True)

        membership = frappe.get_doc({
            "doctype": "CEU Membership",
            "member": "Administrator",
            "plan": "Company Webhook Test Plan",
            "membership_type": "Company",
            "stripe_subscription_id": "sub_test_company_cancel",
            "status": "Active",
            "start_date": today(),
            "end_date": add_years(today(), 1),
            "credit_balance": 0
        }).insert(ignore_permissions=True)

        company = frappe.get_doc({
            "doctype": "Company Account",
            "company_name": "Test Company For Cancellation",
            "billing_email": "Administrator",
            "status": "Active",
            "membership": membership.name,
        }).insert(ignore_permissions=True)

        handle_subscription_deleted({"id": "sub_test_company_cancel"})

        membership.reload()
        company.reload()
        self.assertEqual(membership.status, "Cancelled")
        self.assertEqual(company.status, "Suspended")

    def test_handle_invoice_paid_allocates_credits(self):
        from lms.lms.ceu_stripe_webhooks import handle_invoice_paid

        if not frappe.db.exists("CEU Membership Plan", "Webhook Test Plan"):
            frappe.get_doc({
                "doctype": "CEU Membership Plan",
                "title": "Webhook Test Plan",
                "plan_type": "Professional",
                "ceu_hours": 20.0,
                "price": 199.00,
                "active": 1
            }).insert(ignore_permissions=True)

        membership = frappe.get_doc({
            "doctype": "CEU Membership",
            "member": "Administrator",
            "plan": "Webhook Test Plan",
            "membership_type": "Professional",
            "stripe_subscription_id": "sub_test_webhook",
            "status": "Active",
            "start_date": today(),
            "end_date": add_years(today(), 1),
            "credit_balance": 0
        }).insert(ignore_permissions=True)

        handle_invoice_paid("sub_test_webhook")

        membership.reload()
        self.assertEqual(membership.credit_balance, 20.0)

    def test_one_off_purchase_creates_ledger_entry(self):
        from lms.lms.ceu_stripe_webhooks import _create_one_off_enrollment

        # Need a real course
        courses = frappe.db.get_all("LMS Course", limit=1)
        if not courses:
            self.skipTest("No LMS Course exists for testing")

        course_name = courses[0].name
        user = "Administrator"

        # Delete any existing enrollment for this test
        for e in frappe.db.get_all("LMS Enrollment", {"course": course_name, "member": user}):
            frappe.delete_doc("LMS Enrollment", e.name, force=True, ignore_permissions=True)

        _create_one_off_enrollment(
            course=course_name,
            user=user,
            stripe_payment_id="cs_test_oneoff_789"
        )

        # Should have created a ledger entry
        ledger = frappe.get_last_doc("CEU Credit Ledger", filters={
            "user": user,
            "transaction_type": "Direct Purchase",
            "course": course_name
        })
        self.assertEqual(ledger.stripe_payment_id, "cs_test_oneoff_789")
        self.assertEqual(ledger.hours, 0)

        # Should have created enrollment with credit_source
        enrollment = frappe.get_last_doc("LMS Enrollment", filters={
            "member": user,
            "course": course_name
        })
        self.assertEqual(enrollment.credit_source, "One-Off")

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

    def test_handle_checkout_completed_dispatches_event_one_off(self):
        from lms.lms.ceu_stripe_webhooks import handle_checkout_completed

        with patch("lms.lms.ceu_stripe_webhooks._create_event_registration") as mock_create:
            handle_checkout_completed({
                "id": "cs_test_event_dispatch",
                "payment_intent": "pi_test_evt",
                "amount_total": 7900,
                "currency": "usd",
                "metadata": {
                    "type": "event_one_off",
                    "event": "test-event",
                    "user": "test@test.com",
                },
            })
            mock_create.assert_called_once_with(
                event="test-event",
                user="test@test.com",
                stripe_session_id="cs_test_event_dispatch",
                stripe_payment_intent_id="pi_test_evt",
                amount_total=7900,
                currency="usd",
            )

    def test_create_event_registration_idempotent_on_existing_payment(self):
        from lms.lms.ceu_stripe_webhooks import _create_event_registration

        with patch("lms.lms.ceu_stripe_webhooks.frappe.db.exists", return_value=True) as mock_exists, \
             patch("lms.lms.ceu_stripe_webhooks.frappe.get_doc") as mock_get_doc:
            _create_event_registration(
                event="test-event",
                user="test@test.com",
                stripe_session_id="cs_dup_delivery",
            )
            # First exists() call is the LMS Payment lookup — if it returns True, we must bail
            # before doing any inserts.
            mock_get_doc.assert_not_called()

    def test_invoice_paid_records_stripe_invoice_id(self):
        from lms.lms.ceu_stripe_webhooks import handle_invoice_paid

        if not frappe.db.exists("CEU Membership Plan", "Invoice Test Plan"):
            frappe.get_doc({
                "doctype": "CEU Membership Plan",
                "title": "Invoice Test Plan",
                "plan_type": "Professional",
                "ceu_hours": 15.0,
                "price": 149.00,
                "active": 1
            }).insert(ignore_permissions=True)

        membership = frappe.get_doc({
            "doctype": "CEU Membership",
            "member": "Administrator",
            "plan": "Invoice Test Plan",
            "membership_type": "Professional",
            "stripe_subscription_id": "sub_test_invoice_track",
            "status": "Active",
            "start_date": today(),
            "end_date": add_years(today(), 1),
            "credit_balance": 0
        }).insert(ignore_permissions=True)

        handle_invoice_paid("sub_test_invoice_track", invoice_id="in_test_123")

        ledger = frappe.get_last_doc("CEU Credit Ledger", filters={
            "membership": membership.name,
            "transaction_type": "Allocation"
        })
        self.assertEqual(ledger.stripe_invoice_id, "in_test_123")

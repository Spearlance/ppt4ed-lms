import frappe
from frappe.tests import UnitTestCase
from unittest.mock import patch


class TestEnrollmentConfirmationEmail(UnitTestCase):
    def test_paid_purchase_sends_receipt(self):
        from lms.lms.ceu_enrollment import send_enrollment_confirmation_email

        with patch("lms.lms.utils.lms_send_template_mail") as mock_send:
            send_enrollment_confirmation_email(
                member="Administrator",
                course="test-course",
                credit_source="One-Off",
                amount=49.0,
                currency="USD",
                payment_reference="PAY-TEST-0001",
            )

        mock_send.assert_called_once()
        kwargs = mock_send.call_args.kwargs
        self.assertEqual(kwargs["recipients"], "Administrator")
        self.assertEqual(kwargs["template_name"], "Course Enrollment Confirmation")
        self.assertEqual(kwargs["args"]["payment_reference"], "PAY-TEST-0001")
        self.assertIn("49", kwargs["args"]["amount_display"])

    def test_credit_enrollment_sends_hours_not_amount(self):
        from lms.lms.ceu_enrollment import send_enrollment_confirmation_email

        with patch("lms.lms.utils.lms_send_template_mail") as mock_send:
            send_enrollment_confirmation_email(
                member="Administrator",
                course="test-course",
                credit_source="Company Membership",
                ceu_hours=3.0,
            )

        mock_send.assert_called_once()
        kwargs = mock_send.call_args.kwargs
        self.assertIsNone(kwargs["args"]["amount_display"])
        self.assertEqual(kwargs["args"]["ceu_hours"], 3.0)
        self.assertEqual(kwargs["args"]["credit_source"], "Company Membership")

    def test_mail_failure_fails_open(self):
        from lms.lms.ceu_enrollment import send_enrollment_confirmation_email

        with patch(
            "lms.lms.utils.lms_send_template_mail",
            side_effect=Exception("smtp down"),
        ):
            # Must not raise — enrollment/webhook flow depends on fail-open.
            send_enrollment_confirmation_email(
                member="Administrator",
                course="test-course",
                credit_source="One-Off",
                amount=49.0,
            )

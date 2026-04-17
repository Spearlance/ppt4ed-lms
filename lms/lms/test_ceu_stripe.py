import frappe
from frappe.tests import UnitTestCase
from unittest.mock import patch, MagicMock


class TestCEUStripe(UnitTestCase):
    def test_create_one_off_checkout_session_calls_stripe(self):
        from lms.lms.ceu_stripe import create_one_off_checkout

        mock_session = MagicMock()
        mock_session.url = "https://checkout.stripe.com/test"
        mock_session.id = "cs_test_123"

        mock_course = MagicMock()
        mock_course.title = "Test Course"
        mock_course.paid_course = 1
        mock_course.amount_usd = 49.00
        mock_course.ceu_hours = 2

        frappe.set_user("test@test.com")
        try:
            with patch("lms.lms.ceu_stripe.stripe") as mock_stripe, \
                 patch("lms.lms.ceu_stripe.frappe.get_doc", return_value=mock_course):
                mock_stripe.checkout.Session.create.return_value = mock_session
                result = create_one_off_checkout(course_name="test-course")
                self.assertEqual(result["url"], "https://checkout.stripe.com/test")
                mock_stripe.checkout.Session.create.assert_called_once()
                call_kwargs = mock_stripe.checkout.Session.create.call_args.kwargs
                self.assertEqual(call_kwargs["line_items"][0]["price_data"]["unit_amount"], 4900)
                self.assertEqual(call_kwargs["customer_email"], "test@test.com")
        finally:
            frappe.set_user("Administrator")

    def test_create_subscription_checkout_calls_stripe(self):
        from lms.lms.ceu_stripe import create_subscription_checkout

        mock_session = MagicMock()
        mock_session.url = "https://checkout.stripe.com/sub"
        mock_session.id = "cs_test_sub_456"

        with patch("lms.lms.ceu_stripe.stripe") as mock_stripe:
            mock_stripe.checkout.Session.create.return_value = mock_session
            result = create_subscription_checkout(
                plan_name="Test Pro 20",
                stripe_price_id="price_test_123",
                user_email="test@test.com"
            )
            self.assertEqual(result["url"], "https://checkout.stripe.com/sub")
            mock_stripe.checkout.Session.create.assert_called_once()

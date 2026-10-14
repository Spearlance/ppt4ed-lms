"""LMS Event Registration confirmation: receipt lines and fail-open sending.

Paid events get the same receipt a paid course enrollment gets (amount,
payment reference, purchase date) and a mail failure never rolls back the
registration. Kept off the database: everything the controller reads is
patched.
"""

from datetime import date, datetime, time
from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

MODULE = "lms.lms.doctype.lms_event_registration.lms_event_registration"


class TestReceiptArgs(UnitTestCase):
	def test_paid_registration_gets_receipt_lines(self):
		from lms.lms.doctype.lms_event_registration.lms_event_registration import receipt_args

		payment = frappe._dict(
			name="PAY-0042", amount=79.0, currency="usd", creation=datetime(2026, 10, 14, 9, 30)
		)
		with patch(f"{MODULE}.frappe.db.get_value", return_value=payment):
			args = receipt_args("PAY-0042")

		self.assertEqual(args["payment_reference"], "PAY-0042")
		self.assertIn("79.00", args["amount_display"])
		self.assertTrue(args["purchase_date"])

	def test_free_registration_has_no_receipt(self):
		from lms.lms.doctype.lms_event_registration.lms_event_registration import receipt_args

		self.assertEqual(receipt_args(None)["amount_display"], None)

	def test_zero_dollar_coupon_payment_has_no_receipt(self):
		from lms.lms.doctype.lms_event_registration.lms_event_registration import receipt_args

		payment = frappe._dict(name="PAY-0", amount=0, currency="USD", creation=datetime(2026, 10, 14))
		with patch(f"{MODULE}.frappe.db.get_value", return_value=payment):
			self.assertEqual(receipt_args("PAY-0")["amount_display"], None)


class TestSendMail(UnitTestCase):
	def _doc(self, **overrides):
		doc = frappe._dict(
			doctype="LMS Event Registration",
			name="REG-1",
			event="fall-webinar",
			member="pat@example.com",
			member_name="Pat Example",
			payment="PAY-0042",
			credit_source=None,
		)
		doc.update(overrides)
		return doc

	def _event(self, **overrides):
		row = frappe._dict(
			name="fall-webinar",
			title="Fall Webinar",
			start_date=date(2026, 11, 3),
			start_time=time(9, 0),
			medium="Online",
			zoom_link="https://zoom.us/j/1",
			confirmation_email_template=None,
		)
		row.update(overrides)
		return row

	def _get_value(self, event_row, payment_row, first_name="Pat"):
		def get_value(doctype, name, fields=None, as_dict=False, **kwargs):
			if doctype == "LMS Event":
				return event_row
			if doctype == "LMS Payment":
				return payment_row
			if doctype == "User":
				return first_name
			return None

		return get_value

	def test_paid_registration_email_carries_the_receipt(self):
		from lms.lms.doctype.lms_event_registration.lms_event_registration import send_mail

		payment = frappe._dict(
			name="PAY-0042", amount=79.0, currency="usd", creation=datetime(2026, 10, 14, 9, 30)
		)
		with patch(f"{MODULE}.frappe.db.get_value", side_effect=self._get_value(self._event(), payment)), \
			patch(f"{MODULE}.frappe.db.get_single_value", return_value=None), \
			patch("lms.lms.utils.lms_send_template_mail") as send:
			send_mail(self._doc())

		kwargs = send.call_args.kwargs
		self.assertEqual(kwargs["recipients"], "pat@example.com")
		self.assertEqual(kwargs["template_name"], "Event Registration Confirmation")
		self.assertEqual(kwargs["jinja_template"], "event_enrollment_confirmation")
		args = kwargs["args"]
		self.assertEqual(args["payment_reference"], "PAY-0042")
		self.assertIn("79.00", args["amount_display"])
		self.assertEqual(args["first_name"], "Pat")
		self.assertEqual(args["title"], "Fall Webinar")
		self.assertTrue(args["event_date_display"])
		self.assertTrue(args["event_time_display"])
		self.assertTrue(args["event_url"].endswith("/events/fall-webinar"))

	def test_free_registration_email_has_no_receipt_block(self):
		from lms.lms.doctype.lms_event_registration.lms_event_registration import send_mail

		with patch(f"{MODULE}.frappe.db.get_value", side_effect=self._get_value(self._event(), None)), \
			patch(f"{MODULE}.frappe.db.get_single_value", return_value=None), \
			patch("lms.lms.utils.lms_send_template_mail") as send:
			send_mail(self._doc(payment=None))

		args = send.call_args.kwargs["args"]
		self.assertIsNone(args["amount_display"])
		self.assertIsNone(args["payment_reference"])

	def test_custom_template_on_the_event_still_wins(self):
		from lms.lms.doctype.lms_event_registration.lms_event_registration import send_mail

		event = self._event(confirmation_email_template="My Custom Confirmation")
		with patch(f"{MODULE}.frappe.db.get_value", side_effect=self._get_value(event, None)), \
			patch(f"{MODULE}.frappe.db.get_single_value", return_value="Site Wide Template"), \
			patch("lms.lms.utils.lms_send_template_mail") as send:
			send_mail(self._doc(payment=None))

		self.assertEqual(send.call_args.kwargs["template_name"], "My Custom Confirmation")


class TestAfterInsertFailsOpen(UnitTestCase):
	def test_mail_failure_is_logged_not_raised(self):
		"""A paid registration created by the Stripe webhook must survive a
		mail outage; otherwise Stripe retries and the buyer never gets a seat."""
		doc = frappe.new_doc("LMS Event Registration")
		doc.member = "pat@example.com"
		doc.event = "fall-webinar"

		with patch(f"{MODULE}.send_confirmation_email", side_effect=RuntimeError("smtp down")), \
			patch(f"{MODULE}.queue_signup_webhook") as webhook, \
			patch(f"{MODULE}.frappe.log_error") as log_error, \
			patch.object(doc, "add_member_to_live_class") as live_class:
			doc.after_insert()

		log_error.assert_called_once()
		live_class.assert_called_once()
		webhook.assert_called_once()

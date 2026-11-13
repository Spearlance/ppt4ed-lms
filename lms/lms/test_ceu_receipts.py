"""Read-only receipt tests: every DB/Stripe dependency is mocked; no fixtures written."""

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

import frappe
from jinja2 import Environment

from lms.lms import ceu_receipts as receipts
from lms.lms import ceu_transactions as transactions
from lms.www.purchase_receipt import get_context

BUYER = "garrett-test-receipt@example.com"
OTHER = "garrett-test-other@example.com"


def transaction(**overrides):
	row = frappe._dict(
		{
			"name": "ch_garrett_test_historical",
			"member": BUYER,
			"customer_email": BUYER,
			"member_full_name": "Garrett Test Old Name",
			"status": "Succeeded",
			"gross_amount": 120,
			"refunded_amount": 0,
			"net_amount": 999,  # Deliberately stale: receipts derive the remainder.
			"currency": "USD",
			"transaction_date": "2025-01-02 10:00:00",
			"item_type": "LMS Course",
			"item": "garrett-test-course",
			"item_title": "Garrett Test Course",
			"stripe_payment_intent_id": "pi_garrett_test",
		}
	)
	row.update(overrides)
	return row


def line(title="Garrett Test Course", amount=100, **overrides):
	return {"title": title, "amount": amount, "currency": "USD", "is_upsell": 0, **overrides}


class TestCEUReceipts(TestCase):
	def setUp(self):
		self.row = transaction()
		self.profile = frappe._dict(
			first_name="Garrett", middle_name="Receipt", last_name="Test", full_name="Garrett"
		)
		self.user = patch.object(frappe, "session", SimpleNamespace(user=BUYER))
		self.user.start()
		self.addCleanup(self.user.stop)
		# Locale/number formatting is not this unit's dependency. Frappe 16
		# lazily reads Language/DocType/System Settings while translating or
		# formatting; isolate those helpers before installing strict DB mocks.
		self.addCleanup(patch.stopall)

		def throw(message, exc=frappe.ValidationError, *args, **kwargs):
			raise exc(message)

		# Message-dialog rendering imports its own translation alias on v16.
		# Test permission/validation outcomes, not msgprint's locale/UI plumbing.
		patch.object(frappe, "throw", side_effect=throw).start()
		patch.object(receipts, "_", side_effect=lambda value, *args, **kwargs: value).start()
		patch.object(transactions, "_", side_effect=lambda value, *args, **kwargs: value).start()
		patch.object(
			receipts, "format_datetime", side_effect=lambda value, format_string=None: str(value)
		).start()
		patch.object(
			receipts, "fmt_money", side_effect=lambda value, currency=None: f"{currency} {value:,.2f}"
		).start()
		self.db = patch.object(frappe.db, "get_value", side_effect=self.get_value).start()
		self.admin = patch.object(receipts, "_require_admin", side_effect=frappe.PermissionError).start()
		self.lookup = patch.object(receipts, "_member_for_email", return_value=BUYER).start()
		self.title = patch.object(
			receipts, "_item_title", return_value="Garrett Test Historical Event"
		).start()
		self.lines = []
		self.attach = patch.object(receipts, "_attach_order_lines", side_effect=self.attach_lines).start()
		self.stripe = patch.object(
			transactions, "_stripe", side_effect=AssertionError("No Stripe calls allowed")
		).start()
		self.write = patch.object(
			frappe.db, "set_value", side_effect=AssertionError("No DB writes allowed")
		).start()

	def get_value(self, doctype, name, *args, **kwargs):
		if doctype == "CEU Transaction":
			return deepcopy(self.row)
		if doctype == "User":
			self.assertEqual(name, BUYER)
			return self.profile
		self.fail(f"Unexpected read: {doctype}")

	def attach_lines(self, rows):
		rows[0]["line_items"] = deepcopy(self.lines)

	def receipt(self):
		return receipts.get_purchase_receipt(self.row.name)

	def test_historical_row_has_full_name_provider_and_recorded_amount(self):
		result = self.receipt()
		self.assertEqual(result["buyer_name"], "Garrett Receipt Test")
		self.assertEqual(result["provider"], "PPT4Ed")
		self.assertEqual(result["reference"], self.row.name)
		self.assertIn("120", result["paid_display"])
		self.assertEqual(result["currency"], "USD")
		self.assertTrue(result["purchase_date"])
		self.assertEqual(result["lines"][0]["title"], "Garrett Test Course")
		self.stripe.assert_not_called()
		self.write.assert_not_called()

	def test_guest_denied_before_transaction_lookup(self):
		frappe.session.user = "Guest"
		with self.assertRaises(frappe.PermissionError):
			self.receipt()
		self.db.assert_not_called()

	def test_missing_or_structured_transaction_id_is_denied_without_query(self):
		for value in (None, "", {"member": BUYER}, [self.row.name]):
			with self.assertRaises(frappe.PermissionError):
				receipts.get_purchase_receipt(value)
		self.db.assert_not_called()

	def test_other_buyer_denied_before_reading_profile_or_lines(self):
		frappe.session.user = OTHER
		with self.assertRaises(frappe.PermissionError):
			self.receipt()
		self.assertEqual(self.db.call_count, 1)
		self.attach.assert_not_called()

	def test_billing_email_cannot_override_linked_buyer(self):
		self.row.customer_email = OTHER
		self.assertEqual(self.receipt()["buyer_name"], "Garrett Receipt Test")
		self.lookup.assert_not_called()
		frappe.session.user = OTHER
		with self.assertRaises(frappe.PermissionError):
			self.receipt()

	def test_unlinked_legacy_email_match(self):
		self.row.member = None
		self.assertEqual(self.receipt()["buyer_name"], "Garrett Receipt Test")
		self.lookup.assert_called_once_with(BUYER)

	def test_unlinked_legacy_email_does_not_match_other_buyer(self):
		self.row.member = None
		frappe.session.user = OTHER
		with self.assertRaises(frappe.PermissionError):
			self.receipt()

	def test_authorized_admin_can_view_buyer_not_admin_name(self):
		frappe.session.user = "Administrator"
		self.admin.side_effect = None
		self.assertEqual(self.receipt()["buyer_name"], "Garrett Receipt Test")
		self.admin.assert_called_once()

	def test_nonexistent_and_failed_transactions_denied(self):
		self.db.side_effect = None
		self.db.return_value = None
		with self.assertRaises(frappe.PermissionError):
			self.receipt()
		self.db.side_effect = self.get_value
		for status in ("Failed", "", "Pending"):
			self.row.status = status
			with self.assertRaises(frappe.PermissionError):
				self.receipt()

	def test_course_event_and_order_bump_paid_lines_reconcile(self):
		self.lines = [line("Garrett Test Event", 100), line("Garrett Test Add-on", 20, is_upsell=1)]
		result = self.receipt()
		self.assertEqual(
			[item["title"] for item in result["lines"]], ["Garrett Test Event", "Garrett Test Add-on"]
		)
		self.assertTrue(result["lines"][1]["is_upsell"])
		self.assertFalse(result["allocation_unavailable"])
		self.assertTrue(all(item["amount_display"] for item in result["lines"]))

	def test_existing_paid_line_helper_resolves_primary_event_and_course_addon(self):
		from lms.lms.ceu_reports import _attach_order_lines

		payments = [
			frappe._dict(
				{
					"stripe_payment_intent_id": "pi_garrett_test",
					"stripe_session_id": None,
					"parent_session_id": None,
					"item_type": kind,
					"item": title,
					"title": title,
					"amount": amount,
					"currency": "USD",
					"is_upsell": upsell,
					"upsell_type": "Order Bump" if upsell else None,
				}
			)
			for kind, title, amount, upsell in (
				("LMS Event", "Garrett Test Event", 100, 0),
				("LMS Course", "Garrett Test Course Add-on", 20, 1),
			)
		]
		self.attach.side_effect = _attach_order_lines
		with patch.object(frappe.db, "sql", return_value=payments) as query:
			result = self.receipt()
		self.assertIn("p.payment_received = 1", query.call_args.args[0])
		self.assertEqual(query.call_args.args[1]["intents"], ("pi_garrett_test",))
		self.assertEqual(
			[item["title"] for item in result["lines"]], ["Garrett Test Event", "Garrett Test Course Add-on"]
		)
		self.assertFalse(result["allocation_unavailable"])

	def test_separate_post_purchase_upsell_only_uses_its_own_charge(self):
		self.row.gross_amount = 20
		self.lines = [line("Garrett Test Add-on", 20, is_upsell=1)]
		result = self.receipt()
		self.assertEqual(len(result["lines"]), 1)
		self.assertFalse(result["allocation_unavailable"])

	def test_coupon_mismatch_never_fabricates_item_allocation(self):
		self.lines = [line(amount=129), line("Garrett Test Add-on", 20, is_upsell=1)]
		result = self.receipt()
		self.assertTrue(result["allocation_unavailable"])
		self.assertTrue(all(item["amount_display"] is None for item in result["lines"]))
		self.assertIn("120", result["paid_display"])

	def test_mixed_currency_amounts_never_reconcile(self):
		self.lines = [line(amount=120, currency="EUR")]
		self.assertTrue(self.receipt()["allocation_unavailable"])

	def test_decimal_sums_are_not_float_comparisons(self):
		self.row.gross_amount = 0.3
		self.lines = [line(amount=0.1), line(amount=0.2)]
		self.assertFalse(self.receipt()["allocation_unavailable"])

	def test_legacy_event_title_falls_back_to_existing_item_not_current_price(self):
		self.row.item_title = None
		self.row.item_type = "LMS Event"
		result = self.receipt()
		self.assertEqual(result["lines"][0]["title"], "Garrett Test Historical Event")
		self.assertIsNone(result["lines"][0]["amount_display"])

	def test_historical_invoice_receipt_does_not_require_charge_or_stripe_url(self):
		self.row.name = "in_garrett_test_legacy"
		self.row.stripe_invoice_id = self.row.name
		self.row.item_title = "Garrett Test Membership"
		self.row.stripe_payment_intent_id = None
		self.assertEqual(self.receipt()["lines"][0]["title"], "Garrett Test Membership")
		self.stripe.assert_not_called()

	def test_partial_and_full_refunds_derive_remaining_from_verified_amounts(self):
		for refunded, expected, status in ((20, "100", "Partially Refunded"), (120, "0", "Refunded")):
			self.row.refunded_amount = refunded
			result = self.receipt()
			self.assertEqual(result["status"], status)
			self.assertIn(expected, result["remaining_display"])
			self.assertTrue(result["has_refund"])

	def test_zero_paid_is_preserved_not_replaced_with_catalog_price(self):
		self.row.gross_amount = 0
		result = self.receipt()
		self.assertIn("0", result["paid_display"])
		self.assertFalse(result["has_refund"])

	def test_invalid_or_over_refunded_amounts_fail_closed(self):
		for field, value in (
			("gross_amount", -1),
			("gross_amount", "NaN"),
			("gross_amount", None),
			("refunded_amount", 121),
		):
			self.row = transaction(**{field: value})
			with self.assertRaises(frappe.ValidationError):
				self.receipt()

	def test_missing_name_is_explicit_never_email_or_admin(self):
		self.profile = None
		self.row.member_full_name = None
		result = self.receipt()
		self.assertTrue(result["name_missing"])
		self.assertEqual(result["buyer_name"], "Name not recorded")
		self.assertNotIn("@", result["buyer_name"])

	def test_escaped_names_items_references_in_printable_template(self):
		self.profile.first_name = '<script>alert("buyer")</script>'
		self.row.item_title = '<img src=x onerror="alert(1)">'
		self.row.name = '<script>alert("reference")</script>'
		result = self.receipt()
		template = Path(__file__).parents[1] / "www" / "purchase_receipt.html"
		html = (
			Environment(autoescape=False)
			.from_string(template.read_text())
			.render(receipt=result, _=lambda s: s)
		)
		self.assertNotIn("<script>", html)
		self.assertNotIn("<img src=x", html)
		self.assertIn("&lt;script&gt;", html)
		self.assertIn("@media print", html)
		self.assertIn("window.print()", html)
		self.assertIn("Not itemized", html)
		self.assertNotIn("—", html)
		self.assertIn('<meta name="referrer" content="no-referrer">', html)

	def test_response_headers_on_success_and_denial(self):
		for code in (200, 403, 404, 500):
			response = SimpleNamespace(headers={}, status_code=code)
			receipts.receipt_response_headers(response, SimpleNamespace(path="/purchase_receipt"))
			self.assertIn("no-store", response.headers["Cache-Control"])
			self.assertEqual(response.headers["Referrer-Policy"], "no-referrer")
		response = SimpleNamespace(headers={})
		receipts.receipt_response_headers(response, SimpleNamespace(path="/lms/courses"))
		self.assertEqual(response.headers, {})

	def test_service_worker_excludes_private_receipt_documents(self):
		config = Path(__file__).parents[2] / "frontend" / "vite.config.js"
		self.assertIn(
			"url.pathname.replace(/\\/$/, '') !== '/purchase_receipt'", " ".join(config.read_text().split())
		)

	def test_controller_disables_website_cache_and_sitemap(self):
		with patch.object(frappe, "form_dict", {"transaction": self.row.name}):
			context = frappe._dict()
			get_context(context)
		self.assertEqual(context.no_cache, 1)
		self.assertEqual(context.no_sitemap, 1)
		self.assertEqual(context.receipt["reference"], self.row.name)

	def test_purchase_list_sql_matches_private_receipt_ownership(self):
		with patch.object(frappe.db, "sql", return_value=[]) as query:
			transactions.get_member_purchases()
			sql, params = query.call_args.args
			self.assertIn("COALESCE(t.member, '') = '' AND t.customer_email = %(member)s", sql)
			self.assertEqual(params, {"member": BUYER})
			# No 200-row cutoff hiding older receipts.
			self.assertNotIn("LIMIT 200", sql)
			frappe.session.user = "Guest"
			query.reset_mock()
			with self.assertRaises(frappe.PermissionError):
				transactions.get_member_purchases()
			query.assert_not_called()

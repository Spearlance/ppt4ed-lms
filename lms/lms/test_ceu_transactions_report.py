"""Reports > Money > Transactions: one row per charge with every line item,
the primary purchase named first, and an upsell status that only ever comes
from `LMS Upsell Offer` rows (never inferred from "bought two courses").

Fixtures model the three shapes that matter:

  A  order bump accepted   one charge, two LMS Payment rows (main + add-on)
  B  separate purchases    two charges, two orders, no offer rows at all
  C  order bump declined   one charge, one payment, one Declined offer row
"""

import frappe
from frappe.tests import UnitTestCase
from frappe.utils import now_datetime, nowdate

from lms.lms.ceu_reports import (
	UPSELL_ACCEPTED,
	UPSELL_DECLINED,
	UPSELL_NOT_OFFERED,
	get_transaction_items,
	get_transactions_report,
)

PREFIX = "ch_test_rpt_"
MAIN_TITLE = "Garrett Test Report Main Course"
ADDON_TITLE = "Garrett Test Report Add-on Course"


class TestTransactionsReportLineItems(UnitTestCase):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		self._cleanup()
		self.main = self._ensure_course(MAIN_TITLE, 225)
		self.addon = self._ensure_course(ADDON_TITLE, 30)
		self.today = now_datetime()

		# A: order bump accepted. Molly's case: $225 course + $15 add-on, one charge.
		self._payment("cs_test_rpt_a", "pi_test_rpt_a", self.main, 225)
		self._payment(
			"cs_test_rpt_a", "pi_test_rpt_a", self.addon, 15,
			is_upsell=1, upsell_type="Order Bump", parent_session_id="cs_test_rpt_a",
		)
		self._offer("cs_test_rpt_a:bump", "cs_test_rpt_a", "Order Bump", "Paid", 15)
		# Mis-labelled on purpose: the sync used to pick the add-on as the item.
		self._transaction("a", 240, item=self.addon, intent="pi_test_rpt_a")

		# B: the same two courses bought separately on different days.
		self._payment("cs_test_rpt_b1", "pi_test_rpt_b1", self.main, 225)
		self._payment("cs_test_rpt_b2", "pi_test_rpt_b2", self.addon, 30)
		self._transaction("b1", 225, item=self.main, intent="pi_test_rpt_b1")
		self._transaction("b2", 30, item=self.addon, intent="pi_test_rpt_b2")

		# C: bump shown, box left unticked.
		self._payment("cs_test_rpt_c", "pi_test_rpt_c", self.main, 225)
		self._offer("cs_test_rpt_c:bump", "cs_test_rpt_c", "Order Bump", "Declined", 15)
		self._transaction("c", 225, item=self.main, intent="pi_test_rpt_c")

		# D: an abandoned checkout wrote an offer row but never paid. Must not
		# count as offered or declined.
		self._offer("cs_test_rpt_d:bump", "cs_test_rpt_d", "Order Bump", "Declined", 15)

		frappe.db.commit()

	def tearDown(self):
		self._cleanup()
		frappe.db.commit()
		super().tearDown()

	# ------------------------------------------------------------------ fixtures

	def _cleanup(self):
		for name in frappe.get_all("CEU Transaction", {"stripe_id": ["like", f"{PREFIX}%"]}, pluck="name"):
			frappe.delete_doc("CEU Transaction", name, force=True, ignore_permissions=True)
		for name in frappe.get_all("LMS Upsell Offer", {"parent_session_id": ["like", "cs_test_rpt_%"]}, pluck="name"):
			frappe.delete_doc("LMS Upsell Offer", name, force=True, ignore_permissions=True)
		for name in frappe.get_all("LMS Payment", {"stripe_session_id": ["like", "cs_test_rpt_%"]}, pluck="name"):
			frappe.delete_doc("LMS Payment", name, force=True, ignore_permissions=True)

	def _ensure_course(self, title, amount_usd):
		existing = frappe.db.exists("LMS Course", {"title": title})
		course = frappe.get_doc("LMS Course", existing) if existing else frappe.get_doc({
			"doctype": "LMS Course",
			"title": title,
			"short_introduction": "Transactions report test course.",
			"description": "Transactions report test course.",
			"instructors": [{"instructor": "Administrator"}],
		})
		course.published = 1
		course.paid_course = 1
		course.course_price = amount_usd
		course.amount_usd = amount_usd
		course.currency = "USD"
		course.save(ignore_permissions=True)
		return course.name

	def _payment(self, session, intent, course, amount, **extra):
		return frappe.get_doc({
			"doctype": "LMS Payment",
			"member": "Administrator",
			"billing_name": "Administrator",
			"amount": amount,
			"currency": "USD",
			"payment_for_document_type": "LMS Course",
			"payment_for_document": course,
			"payment_received": 1,
			"stripe_session_id": session,
			"stripe_payment_intent_id": intent,
			**extra,
		}).insert(ignore_permissions=True)

	def _offer(self, key, session, upsell_type, status, price):
		return frappe.get_doc({
			"doctype": "LMS Upsell Offer",
			"offer_key": key,
			"upsell_type": upsell_type,
			"status": status,
			"member": "Administrator",
			"original_course": self.main,
			"upsell_course": self.addon,
			"parent_session_id": session,
			"list_price": price * 2,
			"offer_price": price,
			"discount_pct": 50,
			"currency": "USD",
		}).insert(ignore_permissions=True)

	def _transaction(self, suffix, gross, item, intent):
		doc = frappe.get_doc({
			"doctype": "CEU Transaction",
			"stripe_id": f"{PREFIX}{suffix}",
			"transaction_date": self.today,
			"transaction_type": "Course",
			"status": "Succeeded",
			"gross_amount": gross,
			"refunded_amount": 0,
			"net_amount": gross,
			"currency": "USD",
			"customer_email": "admin@example.com",
			"member": "Administrator",
			"item_type": "LMS Course",
			"item": item,
			"item_title": frappe.db.get_value("LMS Course", item, "title"),
			"stripe_payment_intent_id": intent,
		})
		doc.flags.ignore_permissions = True
		doc.insert()
		return doc

	def _rows(self, **kwargs):
		result = get_transactions_report(from_date=nowdate(), to_date=nowdate(), **kwargs)
		return {r.stripe_id: r for r in result["rows"] if r.stripe_id.startswith(PREFIX)}, result

	# ------------------------------------------------------------------ rows

	def test_order_bump_row_leads_with_primary_purchase_and_lists_both_lines(self):
		rows, _ = self._rows()
		row = rows[f"{PREFIX}a"]

		# The charge was synced with the add-on as its item; the report fixes it.
		self.assertEqual(row.item, self.main)
		self.assertEqual(row.item_title, MAIN_TITLE)
		self.assertEqual(row.gross_amount, 240)

		self.assertEqual([l["title"] for l in row.line_items], [MAIN_TITLE, ADDON_TITLE])
		self.assertEqual([l["amount"] for l in row.line_items], [225, 15])
		self.assertEqual([l["is_upsell"] for l in row.line_items], [0, 1])
		self.assertEqual(sum(l["amount"] for l in row.line_items), row.gross_amount)

		self.assertEqual(row.upsell_status, UPSELL_ACCEPTED)
		self.assertIn(ADDON_TITLE, row.upsell_detail)
		self.assertFalse(row.is_upsell_charge)

	def test_separate_purchases_are_never_an_accepted_upsell(self):
		rows, _ = self._rows()
		for suffix in ("b1", "b2"):
			row = rows[f"{PREFIX}{suffix}"]
			self.assertEqual(row.upsell_status, UPSELL_NOT_OFFERED)
			self.assertEqual(len(row.line_items), 1)
			self.assertFalse(row.has_upsell_line)
		self.assertEqual(rows[f"{PREFIX}b2"].item_title, ADDON_TITLE)

	def test_declined_bump_shows_declined_with_a_single_line(self):
		rows, _ = self._rows()
		row = rows[f"{PREFIX}c"]
		self.assertEqual(row.upsell_status, UPSELL_DECLINED)
		self.assertEqual(len(row.line_items), 1)
		self.assertEqual(row.item_title, MAIN_TITLE)

	def test_rows_without_a_payment_row_still_render(self):
		# Memberships / "Other" charges have no LMS Payment: no lines, not offered.
		doc = self._transaction("x", 10, item=self.main, intent="pi_test_rpt_missing")
		rows, _ = self._rows()
		row = rows[doc.name]
		self.assertEqual(row.line_items, [])
		self.assertEqual(row.upsell_status, UPSELL_NOT_OFFERED)
		self.assertEqual(row.item_title, MAIN_TITLE)

	# ------------------------------------------------------------------ item filter + summary

	def test_item_filter_and_upsell_summary_for_the_main_course(self):
		rows, result = self._rows(item_type="LMS Course", item=self.main)
		self.assertEqual(set(rows), {f"{PREFIX}a", f"{PREFIX}b1", f"{PREFIX}c"})

		summary = result["upsell_summary"]
		self.assertEqual(summary["item"], self.main)
		self.assertEqual(summary["title"], MAIN_TITLE)
		self.assertEqual(summary["orders"], 3)
		# A (accepted) + C (declined). D never paid, so it is not an offer shown.
		self.assertEqual(summary["offered"], 2)
		self.assertEqual(summary["accepted"], 1)
		self.assertEqual(summary["declined"], 1)
		self.assertEqual(summary["acceptance_pct"], 50.0)
		self.assertEqual(summary["upsell_revenue"], 15)

	def test_item_filter_on_the_addon_course_counts_only_its_own_orders(self):
		rows, result = self._rows(item_type="LMS Course", item=self.addon)
		# A paid for it as an add-on, B2 bought it outright.
		self.assertEqual(set(rows), {f"{PREFIX}a", f"{PREFIX}b2"})
		summary = result["upsell_summary"]
		self.assertEqual(summary["orders"], 1)  # b2 only; the add-on line is not an order of it
		self.assertEqual(summary["offered"], 0)
		self.assertEqual(summary["upsell_revenue"], 0)

	def test_unknown_item_type_is_ignored(self):
		_, result = self._rows(item_type="CEU Membership Plan", item="whatever")
		self.assertIsNone(result["upsell_summary"])

	def test_item_picker_lists_paid_courses_once(self):
		items = get_transaction_items()
		mains = [i for i in items if i.item == self.main]
		self.assertEqual(len(mains), 1)
		self.assertEqual(mains[0].item_type, "LMS Course")
		self.assertEqual(mains[0].title, MAIN_TITLE)

	# ------------------------------------------------------------------ sync classification

	def test_sync_classifies_a_bumped_charge_by_its_primary_purchase(self):
		from lms.lms.ceu_transactions import classify_charge

		charge = {
			"id": f"{PREFIX}classify",
			"payment_intent": "pi_test_rpt_a",
			"metadata": {},
			"billing_details": {"email": "admin@example.com"},
		}
		result = classify_charge(charge)
		self.assertEqual(result["classified_by"], "lms_payment")
		self.assertEqual(result["item"], self.main)

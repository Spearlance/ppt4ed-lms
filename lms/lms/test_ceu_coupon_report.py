import frappe
from frappe.tests import UnitTestCase
from frappe.utils import add_days, nowdate


class TestCouponReport(UnitTestCase):
	"""get_coupon_report over real LMS Payment rows: one discounted charge and
	one 100% comp on the same code."""

	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		courses = frappe.get_all("LMS Course", limit=1, pluck="name")
		if not courses:
			self.skipTest("No LMS Course exists for testing")
		self.course = courses[0]

		self._cleanup()
		self.coupon = frappe.get_doc({
			"doctype": "LMS Coupon",
			"enabled": 1,
			"code": "REPORTTEST",
			"discount_type": "Percentage",
			"percentage_discount": 20,
			"redemption_count": 2,
			"applicable_items": [{"reference_doctype": "LMS Course", "reference_name": self.course}],
		}).insert(ignore_permissions=True)

		self.payments = []
		for amount, original, discount in ((24.0, 30.0, 6.0), (0.0, 40.0, 40.0)):
			self.payments.append(
				frappe.get_doc({
					"doctype": "LMS Payment",
					"member": "Administrator",
					"billing_name": "Report Test",
					"amount": amount,
					"original_amount": original,
					"discount_amount": discount,
					"currency": "USD",
					"payment_for_document_type": "LMS Course",
					"payment_for_document": self.course,
					"payment_received": 1,
					"coupon": self.coupon.name,
					"coupon_code": "REPORTTEST",
				}).insert(ignore_permissions=True)
			)

	def tearDown(self):
		self._cleanup()
		super().tearDown()

	def _cleanup(self):
		for name in frappe.get_all("LMS Payment", {"coupon_code": "REPORTTEST"}, pluck="name"):
			frappe.delete_doc("LMS Payment", name, force=True, ignore_permissions=True)
		for name in frappe.get_all("LMS Coupon", {"code": "REPORTTEST"}, pluck="name"):
			frappe.delete_doc("LMS Coupon", name, force=True, ignore_permissions=True)

	def _row(self, rows, key, value):
		return next((r for r in rows if r.get(key) == value), None)

	def test_summary_and_breakdowns(self):
		from lms.lms.ceu_reports import get_coupon_report

		report = get_coupon_report(from_date=add_days(nowdate(), -1), to_date=nowdate())

		code = self._row(report["by_code"], "code", "REPORTTEST")
		self.assertIsNotNone(code)
		self.assertEqual(code["redemptions"], 2)
		self.assertEqual(code["comps"], 1)
		self.assertEqual(code["list_value"], 70.0)
		self.assertEqual(code["discount_given"], 46.0)
		self.assertEqual(code["net_revenue"], 24.0)
		self.assertEqual(code["lifetime_redemptions"], 2)
		self.assertEqual(code["discount_label"], "20% off")

		item = self._row(report["by_item"], "code", "REPORTTEST")
		self.assertIsNotNone(item)
		self.assertEqual(item["item"], self.course)
		self.assertEqual(item["redemptions"], 2)
		self.assertEqual(item["comps"], 1)

		recent = [r for r in report["recent"] if r["code"] == "REPORTTEST"]
		self.assertEqual(len(recent), 2)
		self.assertEqual(sorted(bool(r["is_comp"]) for r in recent), [False, True])

		summary = report["summary"]
		self.assertGreaterEqual(summary["redemptions"], 2)
		self.assertGreaterEqual(summary["comps"], 1)
		self.assertGreaterEqual(summary["discount_given"], 46.0)

	def test_range_excludes_old_payments(self):
		from lms.lms.ceu_reports import get_coupon_report

		report = get_coupon_report(from_date=add_days(nowdate(), -30), to_date=add_days(nowdate(), -2))
		code = self._row(report["by_code"], "code", "REPORTTEST")
		# The code is still listed (admins see every code) but with no usage.
		self.assertIsNotNone(code)
		self.assertEqual(code["redemptions"], 0)
		self.assertEqual(code["net_revenue"], 0)
		self.assertEqual(code["lifetime_redemptions"], 2)

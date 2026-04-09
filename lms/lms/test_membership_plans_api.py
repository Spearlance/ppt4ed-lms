import frappe
from frappe.tests import UnitTestCase

from lms.lms.api import get_membership_plans


class TestGetMembershipPlans(UnitTestCase):
	"""Tests for the get_membership_plans API endpoint."""

	def setUp(self):
		super().setUp()
		# Clean up any plans created by this test class
		frappe.db.delete("CEU Membership Plan", {"title": ["like", "_test_plan_%"]})

	def tearDown(self):
		frappe.db.delete("CEU Membership Plan", {"title": ["like", "_test_plan_%"]})
		super().tearDown()

	def _make_plan(self, title, plan_type, price, ceu_hours, active=1, stripe_price_id=None):
		doc = frappe.get_doc({
			"doctype": "CEU Membership Plan",
			"title": title,
			"plan_type": plan_type,
			"price": price,
			"ceu_hours": ceu_hours,
			"active": active,
			"stripe_price_id": stripe_price_id or "",
		})
		doc.insert(ignore_permissions=True)
		return doc

	def test_returns_only_active_plans(self):
		"""Inactive plans must not appear in the listing."""
		self._make_plan("_test_plan_active", "Professional", 199, 20, active=1)
		self._make_plan("_test_plan_inactive", "Professional", 99, 10, active=0)

		plans = get_membership_plans()
		titles = [p["title"] for p in plans]

		self.assertIn("_test_plan_active", titles)
		self.assertNotIn("_test_plan_inactive", titles)

	def test_returns_required_fields(self):
		"""Each plan dict must expose the fields the frontend needs."""
		self._make_plan("_test_plan_fields", "Company", 899, 100, stripe_price_id="price_abc123")

		plans = get_membership_plans()
		match = next((p for p in plans if p["title"] == "_test_plan_fields"), None)

		self.assertIsNotNone(match, "Plan not found in results")
		for field in ("name", "title", "plan_type", "ceu_hours", "price", "stripe_price_id"):
			self.assertIn(field, match, f"Missing field: {field}")

	def test_ordered_by_price_ascending(self):
		"""Plans must come back cheapest-first so the UI renders correctly."""
		self._make_plan("_test_plan_expensive", "Company", 899, 100)
		self._make_plan("_test_plan_cheap", "Professional", 199, 20)

		plans = get_membership_plans()
		# Filter to just our test plans
		our_plans = [p for p in plans if p["title"] in ("_test_plan_expensive", "_test_plan_cheap")]

		if len(our_plans) == 2:
			self.assertLessEqual(our_plans[0]["price"], our_plans[1]["price"])

	def test_returns_list(self):
		"""Return type must be a list (not None, not a dict)."""
		result = get_membership_plans()
		self.assertIsInstance(result, list)

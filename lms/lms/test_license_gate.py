"""License gate: CEU-bearing signups and registrations need type, state, number.

Background (2026-10-12): the attendee export for a paid event came back with
blank license columns because nothing in the signup → Stripe → registration
funnel ever asked for one. These tests pin the gate at every entry point.

Run on dev with allow_tests toggled on (see memory feedback_run_tests_on_dev):
    bench --site devlms.ppt4ed.org run-tests --module lms.lms.test_license_gate
"""

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import UnitTestCase
from frappe.utils import today

from lms.lms.license import (
	LicenseRequiredError,
	is_license_complete,
	license_required_for_intent,
	license_required_for_target,
	normalize_license,
	require_complete_license,
)

LICENSE = {"license_type": "PT", "license_state": "fl", "professional_license_number": " PT 12345 "}


class TestLicenseGate(UnitTestCase):
	def setUp(self):
		super().setUp()
		# signup_and_enroll / _consume_ppt_signup_token call
		# frappe.local.login_manager.login_as, which only exists inside a web
		# request. Stub it so the full signup path runs under run-tests.
		if not hasattr(frappe.local, "login_manager"):
			frappe.local.login_manager = MagicMock()
			self.addCleanup(lambda: delattr(frappe.local, "login_manager"))

	# ----- fixtures -------------------------------------------------------

	def _delete_user_state(self, email):
		for r in frappe.get_all("LMS Event Registration", filters={"member": email}):
			frappe.delete_doc("LMS Event Registration", r.name, force=True, ignore_permissions=True)
		for e in frappe.get_all("LMS Enrollment", filters={"member": email}):
			frappe.delete_doc("LMS Enrollment", e.name, force=True, ignore_permissions=True)
		for v in frappe.get_all("PPT Enrollment Verification", filters={"email": email}):
			frappe.delete_doc("PPT Enrollment Verification", v.name, force=True, ignore_permissions=True)
		if frappe.db.exists("User", email):
			frappe.delete_doc("User", email, force=True, ignore_permissions=True)

	def _make_user(self, email, **fields):
		self._delete_user_state(email)
		doc = frappe.get_doc({
			"doctype": "User",
			"email": email,
			"first_name": "License",
			"last_name": "Gate",
			"enabled": 1,
			"send_welcome_email": 0,
			"user_type": "Website User",
			**fields,
		})
		doc.flags.ignore_permissions = True
		doc.insert()
		doc.add_roles("LMS Student")
		return doc

	def _ensure_event(self, title, paid=True):
		existing = frappe.db.exists("LMS Event", {"title": title})
		event = frappe.get_doc("LMS Event", existing) if existing else frappe.get_doc({
			"doctype": "LMS Event",
			"title": title,
			"start_date": today(),
			"end_date": today(),
			"start_time": "09:00:00",
			"end_time": "11:00:00",
			"timezone": "America/New_York",
			"description": "License gate test event.",
			"event_details": "<p>License gate test event.</p>",
			"instructors": [{"instructor": "Administrator"}],
		})
		event.published = 1
		event.paid_event = 1 if paid else 0
		event.amount = 100 if paid else 0
		event.amount_usd = 100 if paid else 0
		event.currency = "USD"
		event.allow_self_enrollment = 1
		event.accept_enrollments = 1
		event.save(ignore_permissions=True)
		return event.name

	def _ensure_course(self, title, paid=False, ceu_hours=0, course_type=None):
		existing = frappe.db.exists("LMS Course", {"title": title})
		course = frappe.get_doc("LMS Course", existing) if existing else frappe.get_doc({
			"doctype": "LMS Course",
			"title": title,
			"short_introduction": "License gate test course.",
			"description": "License gate test course.",
			"instructors": [{"instructor": "Administrator"}],
		})
		course.published = 1
		course.paid_course = 1 if paid else 0
		if paid:
			course.course_price = 100
			course.amount_usd = 100
			course.currency = "USD"
		course.ceu_hours = ceu_hours
		if course_type:
			course.course_type = course_type
		course.save(ignore_permissions=True)
		return course.name

	# ----- pure helpers ---------------------------------------------------

	def test_normalize_license_trims_and_uppercases_state(self):
		out = normalize_license(**LICENSE)
		self.assertEqual(out, {
			"license_type": "PT",
			"license_state": "FL",
			"professional_license_number": "PT 12345",
		})

	def test_normalize_license_rejects_missing_fields(self):
		with self.assertRaises(LicenseRequiredError):
			normalize_license("PT", "FL", "")
		with self.assertRaises(LicenseRequiredError):
			normalize_license("", "FL", "123")
		with self.assertRaises(LicenseRequiredError):
			normalize_license("PT", "", "123")

	def test_normalize_license_rejects_unknown_type(self):
		with self.assertRaises(frappe.ValidationError):
			normalize_license("MD", "FL", "123")

	def test_other_type_still_needs_state_and_number(self):
		out = normalize_license("Other", "WA", "14068126")
		self.assertEqual(out["license_type"], "Other")
		with self.assertRaises(LicenseRequiredError):
			normalize_license("Other", "", "")

	def test_license_required_for_target_rules(self):
		paid_event = self._ensure_event("License Gate Paid Event")
		free_event = self._ensure_event("License Gate Free Event", paid=False)
		paid_course = self._ensure_course("License Gate Paid Course", paid=True)
		ceu_course = self._ensure_course("License Gate CEU Course", ceu_hours=2)
		plain_course = self._ensure_course("License Gate Plain Course")
		resource = self._ensure_course("License Gate Resource", ceu_hours=0, course_type="Resource")

		self.assertTrue(license_required_for_target("event", paid_event))
		self.assertTrue(license_required_for_target("event", free_event))
		self.assertTrue(license_required_for_target("course", paid_course))
		self.assertTrue(license_required_for_target("course", ceu_course))
		self.assertFalse(license_required_for_target("course", plain_course))
		self.assertFalse(license_required_for_target("resource", resource))
		self.assertFalse(license_required_for_target("course", resource))
		self.assertFalse(license_required_for_target(None, None))

		self.assertTrue(license_required_for_intent("membership:Individual"))
		self.assertFalse(license_required_for_intent("paid"))
		self.assertFalse(license_required_for_intent(None))

	def test_is_license_complete_and_require(self):
		incomplete = self._make_user("license-gate-incomplete@example.com", license_type="OT")
		complete = self._make_user(
			"license-gate-complete@example.com",
			license_type="OT", license_state="FL", professional_license_number="OT1",
		)
		self.assertFalse(is_license_complete(incomplete.name))
		self.assertTrue(is_license_complete(complete.name))
		with self.assertRaises(LicenseRequiredError):
			require_complete_license(incomplete.name)
		require_complete_license(complete.name)  # no raise

	# ----- signup_and_enroll ---------------------------------------------

	def test_signup_for_event_without_license_is_rejected_and_creates_nothing(self):
		from lms.lms.api import signup_and_enroll

		event = self._ensure_event("License Gate Signup Event")
		email = "license-gate-signup-event@example.com"
		self._delete_user_state(email)

		with self.assertRaises(LicenseRequiredError):
			signup_and_enroll(
				email=email, password="testpass1234", full_name="No License",
				target_type="event", target_slug=event, intent="paid",
			)
		self.assertFalse(frappe.db.exists("User", email))

	def test_signup_for_event_with_license_writes_user_fields(self):
		from lms.lms.api import signup_and_enroll

		event = self._ensure_event("License Gate Signup Event")
		email = "license-gate-signup-event-ok@example.com"
		self._delete_user_state(email)

		original_user = frappe.session.user
		try:
			result = signup_and_enroll(
				email=email, password="testpass1234", full_name="With License",
				target_type="event", target_slug=event, intent="paid", **LICENSE,
			)
		finally:
			frappe.set_user(original_user)

		self.assertEqual(result["status"], "logged_in")
		row = frappe.db.get_value(
			"User", email,
			["license_type", "license_state", "professional_license_number"],
			as_dict=True,
		)
		self.assertEqual(row.license_type, "PT")
		self.assertEqual(row.license_state, "FL")
		self.assertEqual(row.professional_license_number, "PT 12345")

	def test_signup_for_resource_does_not_need_license(self):
		from lms.lms.api import signup_and_enroll

		resource = self._ensure_course("License Gate Resource", course_type="Resource")
		email = "license-gate-signup-resource@example.com"
		self._delete_user_state(email)

		original_user = frappe.session.user
		try:
			result = signup_and_enroll(
				email=email, password="testpass1234", full_name="Resource Only",
				target_type="resource", target_slug=resource, intent="free",
			)
		finally:
			frappe.set_user(original_user)

		self.assertEqual(result["status"], "logged_in")
		self.assertTrue(frappe.db.exists("User", email))
		self.assertFalse(is_license_complete(email))

	def test_signup_existing_email_pivots_before_license_check(self):
		"""A returning user who types into the signup tab must get the
		"exists" pivot, not a license error, even with the fields blank."""
		from lms.lms.api import signup_and_enroll

		event = self._ensure_event("License Gate Signup Event")
		existing = self._make_user("license-gate-existing@example.com")
		result = signup_and_enroll(
			email=existing.name, password="testpass1234", full_name="Existing",
			target_type="event", target_slug=event, intent="paid",
		)
		self.assertEqual(result["status"], "exists")

	def test_ppt_signup_carries_license_through_verification(self):
		from lms.lms.api import _consume_ppt_signup_token, signup_and_enroll

		event = self._ensure_event("License Gate Signup Event")
		email = "license-gate-ppt@ppt4kids.com"
		self._delete_user_state(email)

		with patch("lms.lms.api.lms_send_template_mail"):
			result = signup_and_enroll(
				email=email, password="testpass1234", full_name="PPT License",
				target_type="event", target_slug=event, intent="paid", **LICENSE,
			)
		self.assertEqual(result["status"], "verification_sent")
		held = frappe.db.get_value(
			"PPT Enrollment Verification", {"email": email, "used": 0},
			["license_type", "license_state", "professional_license_number"], as_dict=True,
		)
		self.assertEqual(held.license_state, "FL")

		token = frappe.db.get_value("PPT Enrollment Verification", {"email": email}, "token")
		original_user = frappe.session.user
		try:
			_consume_ppt_signup_token(token)
		finally:
			frappe.set_user(original_user)

		self.assertTrue(is_license_complete(email))

	# ----- logged-in entry points ----------------------------------------

	def _as(self, email):
		original_user = frappe.session.user
		frappe.set_user(email)
		return original_user

	def test_create_event_checkout_requires_license(self):
		from lms.lms.ceu_stripe import create_event_checkout

		event = self._ensure_event("License Gate Checkout Event")
		user = self._make_user("license-gate-checkout@example.com")
		original = self._as(user.name)
		try:
			with self.assertRaises(LicenseRequiredError):
				create_event_checkout(event)
		finally:
			frappe.set_user(original)

	def test_create_one_off_checkout_requires_license(self):
		from lms.lms.ceu_stripe import create_one_off_checkout

		course = self._ensure_course("License Gate Paid Course", paid=True)
		user = self._make_user("license-gate-checkout-course@example.com")
		original = self._as(user.name)
		try:
			with self.assertRaises(LicenseRequiredError):
				create_one_off_checkout(course)
		finally:
			frappe.set_user(original)

	def test_register_for_free_event_requires_license_then_registers(self):
		from lms.lms.api import register_for_free_event

		event = self._ensure_event("License Gate Free Event", paid=False)
		user = self._make_user("license-gate-free-event@example.com")
		original = self._as(user.name)
		try:
			with self.assertRaises(LicenseRequiredError):
				register_for_free_event(event)
			frappe.db.set_value("User", user.name, normalize_license(**LICENSE))
			result = register_for_free_event(event)
			self.assertEqual(result["status"], "registered")
			self.assertTrue(frappe.db.exists(
				"LMS Event Registration", {"event": event, "member": user.name}
			))
		finally:
			frappe.set_user(original)

	def test_save_my_license_writes_current_user(self):
		from lms.lms.license import save_my_license

		user = self._make_user("license-gate-save@example.com")
		original = self._as(user.name)
		try:
			out = save_my_license("SLP", "wa", " 14068126 ")
		finally:
			frappe.set_user(original)
		self.assertTrue(out["license_complete"])
		row = frappe.db.get_value(
			"User", user.name,
			["license_type", "license_state", "professional_license_number"], as_dict=True,
		)
		self.assertEqual((row.license_type, row.license_state, row.professional_license_number),
		                 ("SLP", "WA", "14068126"))

	def test_get_user_info_reports_license_complete(self):
		from lms.lms.api import get_user_info

		user = self._make_user(
			"license-gate-userinfo@example.com",
			license_type="OT", license_state="FL", professional_license_number="OT1",
		)
		original = self._as(user.name)
		try:
			info = get_user_info()
		finally:
			frappe.set_user(original)
		self.assertTrue(info.license_complete)
		self.assertEqual(info.license_state, "FL")

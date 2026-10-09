import frappe
from frappe.tests import UnitTestCase
from unittest.mock import MagicMock, patch

from lms.lms import ceu_coupon


def _coupon(**overrides):
	coupon = {
		"name": "cpn-1",
		"code": "SAVE20",
		"expires_on": None,
		"usage_limit": 0,
		"redemption_count": 0,
		"discount_type": "Percentage",
		"percentage_discount": 20,
		"fixed_amount_discount": 0,
	}
	coupon.update(overrides)
	return frappe._dict(coupon)


class TestCouponMath(UnitTestCase):
	def test_percentage_rounds_half_up_to_the_cent(self):
		# 20% of $49.99 = $9.998 -> $10.00
		self.assertEqual(ceu_coupon.discount_cents(4999, _coupon()), 1000)

	def test_percentage_is_clamped_to_0_100(self):
		self.assertEqual(ceu_coupon.discount_cents(1000, _coupon(percentage_discount=150)), 1000)
		self.assertEqual(ceu_coupon.discount_cents(1000, _coupon(percentage_discount=-5)), 0)

	def test_fixed_amount_never_exceeds_the_price(self):
		coupon = _coupon(discount_type="Fixed Amount", fixed_amount_discount=75)
		self.assertEqual(ceu_coupon.discount_cents(4900, coupon), 4900)
		self.assertEqual(ceu_coupon.discount_cents(9900, coupon), 7500)

	def test_price_with_coupon_breakdown(self):
		pricing = ceu_coupon.price_with_coupon(49.0, _coupon())
		self.assertEqual(pricing["original_cents"], 4900)
		self.assertEqual(pricing["discount_cents"], 980)
		self.assertEqual(pricing["final_cents"], 3920)
		self.assertEqual(pricing["final_usd"], 39.2)
		self.assertEqual(pricing["label"], "20% off")
		self.assertFalse(pricing["is_free"])

	def test_hundred_percent_is_free(self):
		pricing = ceu_coupon.price_with_coupon(49.0, _coupon(percentage_discount=100))
		self.assertEqual(pricing["final_cents"], 0)
		self.assertTrue(pricing["is_free"])

	def test_fixed_label(self):
		self.assertEqual(
			ceu_coupon.describe_discount(_coupon(discount_type="Fixed Amount", fixed_amount_discount=10)),
			"$10 off",
		)

	def test_metadata_round_trip(self):
		pricing = ceu_coupon.price_with_coupon(49.0, _coupon())
		metadata = ceu_coupon.checkout_metadata(pricing)
		# Stripe metadata values must be strings.
		self.assertTrue(all(isinstance(v, str) for v in metadata.values()))
		fields = ceu_coupon.payment_fields_from_metadata(metadata)
		self.assertEqual(fields["coupon"], "cpn-1")
		self.assertEqual(fields["coupon_code"], "SAVE20")
		self.assertEqual(fields["original_amount"], 49.0)
		self.assertEqual(fields["discount_amount"], 9.8)

	def test_no_coupon_metadata_gives_none(self):
		self.assertIsNone(ceu_coupon.payment_fields_from_metadata({"type": "one_off"}))
		self.assertIsNone(ceu_coupon.payment_fields_from_metadata(None))


class TestResolveCoupon(UnitTestCase):
	"""Validation chain, with the DB mocked."""

	def _resolve(self, coupon, exists_side_effect=None, doctype="LMS Course", code="save20"):
		def exists(dt, filters=None, *args, **kwargs):
			if dt == "LMS Coupon":
				return coupon["name"] if coupon is not None else None
			if dt == "LMS Coupon Item":
				return exists_side_effect if exists_side_effect is not None else "row-1"
			return None

		with patch("lms.lms.ceu_coupon.frappe.db.exists", side_effect=exists), \
			patch("lms.lms.ceu_coupon.frappe.db.get_value", return_value=coupon):
			return ceu_coupon.resolve_coupon(doctype, "some-item", code)

	def test_code_is_normalised_and_returned(self):
		resolved = self._resolve(_coupon(), code="  save20 ")
		self.assertEqual(resolved["code"], "SAVE20")

	def test_unknown_code_is_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			self._resolve(None)

	def test_expired_coupon_is_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			self._resolve(_coupon(expires_on="2000-01-01"))

	def test_usage_limit_is_enforced(self):
		with self.assertRaises(frappe.ValidationError):
			self._resolve(_coupon(usage_limit=5, redemption_count=5))
		# Under the limit still works.
		self._resolve(_coupon(usage_limit=5, redemption_count=4))

	def test_coupon_must_list_the_item(self):
		with self.assertRaises(frappe.ValidationError):
			self._resolve(_coupon(), exists_side_effect=False)

	def test_events_are_supported_like_courses(self):
		resolved = self._resolve(_coupon(), doctype="LMS Event")
		self.assertEqual(resolved["name"], "cpn-1")

	def test_other_doctypes_are_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			self._resolve(_coupon(), doctype="LMS Batch")

	def test_sub_minimum_total_is_rejected(self):
		coupon = _coupon(discount_type="Fixed Amount", fixed_amount_discount=49)
		with patch("lms.lms.ceu_coupon.resolve_coupon", return_value=coupon):
			with self.assertRaises(frappe.ValidationError):
				ceu_coupon.apply_coupon("LMS Course", "c", "X", 49.25)


def _mock_course(amount_usd=49.0):
	course = MagicMock()
	course.title = "Test Course"
	course.paid_course = 1
	course.amount_usd = amount_usd
	course.ceu_hours = 2
	return course


def _mock_event(amount=99.0):
	event = MagicMock()
	event.title = "Test Event"
	event.paid_event = 1
	event.currency = "USD"
	event.amount = amount
	event.amount_usd = amount
	event.early_bird_deadline = None
	event.credit_hours = 3
	event.seat_count = 0
	return event


SETTINGS_OFF = {"order_bump": False, "post_purchase": False, "discount_pct": 50}


class TestCouponAtCheckout(UnitTestCase):
	def _course_checkout(self, coupon, coupon_code="SAVE20"):
		from lms.lms.ceu_stripe import create_one_off_checkout

		mock_session = MagicMock()
		mock_session.url = "https://checkout.stripe.com/test"
		mock_session.id = "cs_test_123"

		frappe.set_user("test@test.com")
		try:
			with patch("lms.lms.ceu_stripe.stripe") as mock_stripe, \
				patch("lms.lms.api._is_ppt_employee_email", return_value=False), \
				patch("lms.lms.ceu_stripe.frappe.get_doc", return_value=_mock_course()), \
				patch("lms.lms.ceu_upsell.get_upsell_settings", return_value=SETTINGS_OFF), \
				patch("lms.lms.ceu_coupon.resolve_coupon", return_value=coupon), \
				patch("lms.lms.ceu_coupon.enroll_free_course") as enroll_free:
				mock_stripe.checkout.Session.create.return_value = mock_session
				result = create_one_off_checkout(course_name="main-course", coupon_code=coupon_code)
				return result, mock_stripe, enroll_free
		finally:
			frappe.set_user("Administrator")

	def test_course_checkout_without_coupon_is_unchanged(self):
		result, mock_stripe, _ = self._course_checkout(_coupon(), coupon_code=None)
		kwargs = mock_stripe.checkout.Session.create.call_args.kwargs
		self.assertEqual(kwargs["line_items"][0]["price_data"]["unit_amount"], 4900)
		self.assertNotIn("coupon", kwargs["metadata"])
		self.assertEqual(result["url"], "https://checkout.stripe.com/test")

	def test_course_checkout_discounts_line_item_and_tags_metadata(self):
		_, mock_stripe, enroll_free = self._course_checkout(_coupon())
		kwargs = mock_stripe.checkout.Session.create.call_args.kwargs
		self.assertEqual(kwargs["line_items"][0]["price_data"]["unit_amount"], 3920)
		self.assertIn("SAVE20", kwargs["line_items"][0]["price_data"]["product_data"]["description"])
		self.assertEqual(kwargs["metadata"]["coupon"], "cpn-1")
		self.assertEqual(kwargs["metadata"]["coupon_code"], "SAVE20")
		self.assertEqual(kwargs["metadata"]["original_cents"], "4900")
		self.assertEqual(kwargs["metadata"]["discount_cents"], "980")
		enroll_free.assert_not_called()

	def test_free_course_coupon_skips_stripe(self):
		enroll_result = {"status": "enrolled", "redirect_to": "/lms/courses/main-course"}
		coupon = _coupon(percentage_discount=100)
		from lms.lms.ceu_stripe import create_one_off_checkout

		frappe.set_user("test@test.com")
		try:
			with patch("lms.lms.ceu_stripe.stripe") as mock_stripe, \
				patch("lms.lms.api._is_ppt_employee_email", return_value=False), \
				patch("lms.lms.ceu_stripe.frappe.get_doc", return_value=_mock_course()), \
				patch("lms.lms.ceu_coupon.resolve_coupon", return_value=coupon), \
				patch("lms.lms.ceu_coupon.enroll_free_course", return_value=enroll_result) as enroll_free:
				result = create_one_off_checkout(course_name="main-course", coupon_code="FREE")
				self.assertEqual(result, enroll_result)
				mock_stripe.checkout.Session.create.assert_not_called()
				pricing = enroll_free.call_args.args[2]
				self.assertTrue(pricing["is_free"])
				self.assertEqual(enroll_free.call_args.args[1], "test@test.com")
		finally:
			frappe.set_user("Administrator")

	def test_event_checkout_discounts_line_item_and_tags_metadata(self):
		from lms.lms.ceu_stripe import create_event_checkout

		mock_session = MagicMock()
		mock_session.url = "https://checkout.stripe.com/event"
		mock_session.id = "cs_test_event"

		frappe.set_user("test@test.com")
		try:
			with patch("lms.lms.ceu_stripe.stripe") as mock_stripe, \
				patch("lms.lms.api._is_ppt_employee_email", return_value=False), \
				patch("lms.lms.ceu_stripe.frappe.get_doc", return_value=_mock_event()), \
				patch("lms.lms.ceu_stripe.frappe.db.exists", return_value=False), \
				patch("lms.lms.ceu_upsell.get_upsell_settings", return_value=SETTINGS_OFF), \
				patch("lms.lms.ceu_coupon.resolve_coupon", return_value=_coupon()) as resolve:
				mock_stripe.checkout.Session.create.return_value = mock_session
				create_event_checkout(event_name="main-event", coupon_code="save20")
				kwargs = mock_stripe.checkout.Session.create.call_args.kwargs
				self.assertEqual(resolve.call_args.args[0], "LMS Event")
				self.assertEqual(resolve.call_args.args[1], "main-event")
				# 20% off $99 = $19.80 -> $79.20
				self.assertEqual(kwargs["line_items"][0]["price_data"]["unit_amount"], 7920)
				self.assertEqual(kwargs["metadata"]["type"], "event_one_off")
				self.assertEqual(kwargs["metadata"]["coupon"], "cpn-1")
				self.assertEqual(kwargs["metadata"]["discount_cents"], "1980")
		finally:
			frappe.set_user("Administrator")

	def test_free_event_coupon_skips_stripe(self):
		from lms.lms.ceu_stripe import create_event_checkout

		register_result = {"status": "enrolled", "redirect_to": "/lms/events/main-event"}
		frappe.set_user("test@test.com")
		try:
			with patch("lms.lms.ceu_stripe.stripe") as mock_stripe, \
				patch("lms.lms.api._is_ppt_employee_email", return_value=False), \
				patch("lms.lms.ceu_stripe.frappe.get_doc", return_value=_mock_event()), \
				patch("lms.lms.ceu_stripe.frappe.db.exists", return_value=False), \
				patch("lms.lms.ceu_coupon.resolve_coupon", return_value=_coupon(percentage_discount=100)), \
				patch("lms.lms.ceu_coupon.register_free_event", return_value=register_result) as register:
				result = create_event_checkout(event_name="main-event", coupon_code="FREE")
				self.assertEqual(result, register_result)
				mock_stripe.checkout.Session.create.assert_not_called()
				register.assert_called_once()
		finally:
			frappe.set_user("Administrator")


class TestEventPricing(UnitTestCase):
	def test_usd_event_uses_amount(self):
		event = _mock_event(amount=99.0)
		event.amount_usd = 0
		self.assertEqual(ceu_coupon.event_usd_price(event), (99.0, False))

	def test_non_usd_event_uses_amount_usd(self):
		event = _mock_event()
		event.currency = "INR"
		event.amount = 8000
		event.amount_usd = 95.0
		self.assertEqual(ceu_coupon.event_usd_price(event), (95.0, False))

	def test_early_bird_applies_before_deadline(self):
		from frappe.utils import add_days, nowdate

		event = _mock_event(amount=99.0)
		event.early_bird_deadline = add_days(nowdate(), 3)
		event.early_bird_amount = 79.0
		event.early_bird_amount_usd = 79.0
		self.assertEqual(ceu_coupon.event_usd_price(event), (79.0, True))

	def test_early_bird_ignored_after_deadline(self):
		from frappe.utils import add_days, nowdate

		event = _mock_event(amount=99.0)
		event.early_bird_deadline = add_days(nowdate(), -1)
		event.early_bird_amount = 79.0
		event.early_bird_amount_usd = 79.0
		self.assertEqual(ceu_coupon.event_usd_price(event), (99.0, False))

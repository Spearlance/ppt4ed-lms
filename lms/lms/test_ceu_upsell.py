import frappe
import stripe
from frappe.tests import UnitTestCase
from unittest.mock import patch, MagicMock

from lms.lms import ceu_upsell


SETTINGS_OFF = {"order_bump": False, "post_purchase": False, "discount_pct": 50}
SETTINGS_BUMP = {"order_bump": True, "post_purchase": False, "discount_pct": 50}
SETTINGS_POST = {"order_bump": False, "post_purchase": True, "discount_pct": 50}
SETTINGS_BOTH = {"order_bump": True, "post_purchase": True, "discount_pct": 50}

OFFER = {
	"course": "related-course",
	"title": "Related Course",
	"image": None,
	"short_introduction": "More learning",
	"ceu_hours": 1.5,
	"list_price_usd": 49.0,
	"offer_price_usd": 24.5,
	"offer_price_cents": 2450,
	"discount_pct": 50,
}


def _mock_course(title="Test Course", amount_usd=49.0, ceu_hours=2):
	course = MagicMock()
	course.title = title
	course.paid_course = 1
	course.amount_usd = amount_usd
	course.ceu_hours = ceu_hours
	return course


def _mock_session(**overrides):
	"""A paid one-off Checkout Session as `stripe.checkout.Session.retrieve` returns it."""
	session = {
		"id": "cs_test_parent",
		"payment_status": "paid",
		"customer": "cus_123",
		"payment_intent": {"id": "pi_parent", "payment_method": "pm_card"},
		"metadata": {"type": "one_off", "course": "main-course", "user": "test@test.com"},
	}
	session.update(overrides)
	return session


def _mock_intent(status="succeeded", intent_id="pi_upsell"):
	intent = MagicMock()
	intent.id = intent_id
	intent.get.side_effect = lambda key, default=None: {"status": status, "id": intent_id}.get(key, default)
	return intent


class TestUpsellSelection(UnitTestCase):
	def test_settings_default_discount_when_unset(self):
		for stored in (None, 0, "0"):
			single = MagicMock()
			single.get.side_effect = lambda key, _s=stored: {"upsell_discount_pct": _s}.get(key, 0)
			with patch("lms.lms.ceu_upsell.frappe.get_single", return_value=single):
				settings = ceu_upsell.get_upsell_settings()
			self.assertEqual(settings["discount_pct"], 50)
			self.assertFalse(settings["order_bump"])
			self.assertFalse(settings["post_purchase"])

		single = MagicMock()
		single.get.side_effect = lambda key: {"upsell_discount_pct": 30, "enable_order_bump": 1}.get(key, 0)
		with patch("lms.lms.ceu_upsell.frappe.get_single", return_value=single):
			settings = ceu_upsell.get_upsell_settings()
		self.assertEqual(settings["discount_pct"], 30)
		self.assertTrue(settings["order_bump"])

	def test_price_is_rounded_to_cents_and_never_negative(self):
		self.assertEqual(ceu_upsell.upsell_price_cents(49.0, 50), 2450)
		self.assertEqual(ceu_upsell.upsell_price_cents(19.99, 50), 1000)
		self.assertEqual(ceu_upsell.upsell_price_cents(29.99, 50), 1500)
		self.assertEqual(ceu_upsell.upsell_price_cents(10, 0), 1000)
		self.assertEqual(ceu_upsell.upsell_price_cents(10, 100), 0)
		self.assertEqual(ceu_upsell.upsell_price_cents(10, 150), 0)
		self.assertEqual(ceu_upsell.upsell_price_cents(None, 50), 0)

	def test_get_upsell_course_returns_none_for_staff(self):
		with patch("lms.lms.api._is_ppt_employee_email", return_value=True), \
			patch("lms.lms.ceu_upsell.frappe.get_all") as get_all:
			self.assertIsNone(ceu_upsell.get_upsell_course("main", "staff@ppt.com", 50))
			get_all.assert_not_called()

	def test_get_upsell_course_skips_ineligible_and_owned(self):
		courses = {
			"unpublished": {"published": 0, "paid_course": 1, "amount_usd": 40, "disable_self_learning": 0},
			"free": {"published": 1, "paid_course": 0, "amount_usd": 0, "disable_self_learning": 0},
			"unpriced": {"published": 1, "paid_course": 1, "amount_usd": 0, "disable_self_learning": 0},
			"too-cheap": {"published": 1, "paid_course": 1, "amount_usd": 0.5, "disable_self_learning": 0},
			"owned": {"published": 1, "paid_course": 1, "amount_usd": 40, "disable_self_learning": 0},
			"excluded": {"published": 1, "paid_course": 1, "amount_usd": 40, "disable_self_learning": 0},
			"good": {"published": 1, "paid_course": 1, "amount_usd": 40, "disable_self_learning": 0},
		}

		def get_value(doctype, name, fields, as_dict=False):
			return frappe._dict(courses[name])

		def exists(doctype, filters):
			return filters.get("course") == "owned"

		with patch("lms.lms.api._is_ppt_employee_email", return_value=False), \
			patch("lms.lms.ceu_upsell.frappe.get_all", return_value=list(courses)), \
			patch("lms.lms.ceu_upsell.frappe.db.get_value", side_effect=get_value), \
			patch("lms.lms.ceu_upsell.frappe.db.exists", side_effect=exists):
			result = ceu_upsell.get_upsell_course("main", "test@test.com", 50, exclude={"excluded"})
		self.assertEqual(result, "good")

	def test_get_upsell_course_none_without_related_courses(self):
		with patch("lms.lms.api._is_ppt_employee_email", return_value=False), \
			patch("lms.lms.ceu_upsell.frappe.get_all", return_value=[]):
			self.assertIsNone(ceu_upsell.get_upsell_course("main", "test@test.com", 50))


class TestCheckoutWithUpsells(UnitTestCase):
	"""create_one_off_checkout with the flags on."""

	def _checkout(self, settings, add_upsell=0, upsell_course="related-course"):
		from lms.lms.ceu_stripe import create_one_off_checkout

		mock_session = MagicMock()
		mock_session.url = "https://checkout.stripe.com/test"
		mock_session.id = "cs_test_123"

		frappe.set_user("test@test.com")
		try:
			with patch("lms.lms.ceu_stripe.stripe") as mock_stripe, \
				patch("lms.lms.ceu_stripe.frappe.get_doc", return_value=_mock_course()), \
				patch("lms.lms.ceu_upsell.get_upsell_settings", return_value=settings), \
				patch("lms.lms.ceu_upsell.get_upsell_course", return_value=upsell_course), \
				patch("lms.lms.ceu_upsell.describe_offer", return_value=dict(OFFER)), \
				patch("lms.lms.ceu_upsell.find_or_create_customer", return_value="cus_123"), \
				patch("lms.lms.ceu_upsell.record_offer") as record_offer:
				mock_stripe.checkout.Session.create.return_value = mock_session
				result = create_one_off_checkout(course_name="main-course", add_upsell=add_upsell)
				kwargs = mock_stripe.checkout.Session.create.call_args.kwargs
				return result, kwargs, record_offer
		finally:
			frappe.set_user("Administrator")

	def test_flags_off_keeps_legacy_checkout(self):
		_, kwargs, record_offer = self._checkout(SETTINGS_OFF, add_upsell=1)
		self.assertEqual(len(kwargs["line_items"]), 1)
		self.assertEqual(kwargs["customer_email"], "test@test.com")
		self.assertNotIn("customer", kwargs)
		self.assertNotIn("payment_intent_data", kwargs)
		self.assertNotIn("upsell_course", kwargs["metadata"])
		self.assertIn("/lms/courses/main-course?payment=success", kwargs["success_url"])
		record_offer.assert_not_called()

	def test_no_related_course_changes_nothing(self):
		_, kwargs, record_offer = self._checkout(SETTINGS_BOTH, add_upsell=1, upsell_course=None)
		self.assertEqual(len(kwargs["line_items"]), 1)
		self.assertEqual(kwargs["customer_email"], "test@test.com")
		self.assertIn("/lms/courses/main-course?payment=success", kwargs["success_url"])
		record_offer.assert_not_called()

	def test_order_bump_adds_discounted_line_item_and_metadata(self):
		_, kwargs, record_offer = self._checkout(SETTINGS_BUMP, add_upsell=1)
		self.assertEqual(len(kwargs["line_items"]), 2)
		bump = kwargs["line_items"][1]["price_data"]
		self.assertEqual(bump["unit_amount"], 2450)
		self.assertEqual(bump["product_data"]["metadata"]["course"], "related-course")
		self.assertIn("50% off", bump["product_data"]["name"])
		self.assertEqual(kwargs["metadata"]["upsell_course"], "related-course")
		self.assertEqual(kwargs["metadata"]["upsell_cents"], "2450")
		# Bump only: no card saving, no offer page.
		self.assertEqual(kwargs["customer_email"], "test@test.com")
		self.assertIn("/lms/courses/main-course?payment=success", kwargs["success_url"])
		record_offer.assert_called_once()
		self.assertEqual(record_offer.call_args.kwargs["status"], "Accepted")

	def test_order_bump_unticked_records_decline_and_adds_nothing(self):
		_, kwargs, record_offer = self._checkout(SETTINGS_BUMP, add_upsell=0)
		self.assertEqual(len(kwargs["line_items"]), 1)
		self.assertNotIn("upsell_course", kwargs["metadata"])
		self.assertEqual(record_offer.call_args.kwargs["status"], "Declined")

	def test_post_purchase_saves_card_and_routes_to_offer_page(self):
		_, kwargs, _ = self._checkout(SETTINGS_POST)
		self.assertEqual(kwargs["customer"], "cus_123")
		self.assertNotIn("customer_email", kwargs)
		self.assertEqual(kwargs["payment_intent_data"], {"setup_future_usage": "off_session"})
		self.assertEqual(kwargs["custom_text"]["submit"]["message"], ceu_upsell.SAVE_CARD_CONSENT)
		self.assertIn("/lms/upsell?session_id={CHECKOUT_SESSION_ID}", kwargs["success_url"])
		self.assertEqual(len(kwargs["line_items"]), 1)

	def test_taken_bump_skips_post_purchase_setup(self):
		_, kwargs, _ = self._checkout(SETTINGS_BOTH, add_upsell=1)
		self.assertEqual(len(kwargs["line_items"]), 2)
		self.assertEqual(kwargs["customer_email"], "test@test.com")
		self.assertNotIn("payment_intent_data", kwargs)
		self.assertIn("/lms/courses/main-course?payment=success", kwargs["success_url"])


class TestWebhookUpsells(UnitTestCase):
	def test_order_bump_enrolls_both_courses_with_split_amounts(self):
		from lms.lms.ceu_stripe_webhooks import handle_checkout_completed

		data = {
			"id": "cs_test_bump",
			"payment_intent": "pi_bump",
			"amount_total": 7350,
			"currency": "usd",
			"metadata": {
				"type": "one_off",
				"course": "main-course",
				"user": "test@test.com",
				"upsell_course": "related-course",
				"upsell_cents": "2450",
			},
		}
		with patch("lms.lms.ceu_stripe_webhooks._create_one_off_enrollment", return_value="PAY-1") as enroll, \
			patch("lms.lms.ceu_upsell.mark_offer_paid") as mark_paid:
			handle_checkout_completed(data)

		self.assertEqual(enroll.call_count, 2)
		main_kwargs, bump_kwargs = (c.kwargs for c in enroll.call_args_list)
		self.assertEqual(main_kwargs["course"], "main-course")
		self.assertEqual(main_kwargs["amount_total"], 4900)
		self.assertEqual(main_kwargs["is_upsell"], 0)
		self.assertEqual(bump_kwargs["course"], "related-course")
		self.assertEqual(bump_kwargs["amount_total"], 2450)
		self.assertEqual(bump_kwargs["is_upsell"], 1)
		self.assertEqual(bump_kwargs["upsell_type"], ceu_upsell.ORDER_BUMP)
		self.assertEqual(bump_kwargs["parent_session_id"], "cs_test_bump")
		self.assertEqual(bump_kwargs["stripe_session_id"], "cs_test_bump")
		mark_paid.assert_called_once()

	def test_plain_one_off_enrolls_once_with_full_amount(self):
		from lms.lms.ceu_stripe_webhooks import handle_checkout_completed

		data = {
			"id": "cs_test_plain",
			"payment_intent": "pi_plain",
			"amount_total": 4900,
			"currency": "usd",
			"metadata": {"type": "one_off", "course": "main-course", "user": "test@test.com"},
		}
		with patch("lms.lms.ceu_stripe_webhooks._create_one_off_enrollment", return_value="PAY-1") as enroll, \
			patch("lms.lms.ceu_upsell.mark_offer_paid") as mark_paid:
			handle_checkout_completed(data)

		enroll.assert_called_once()
		self.assertEqual(enroll.call_args.kwargs["amount_total"], 4900)
		self.assertEqual(enroll.call_args.kwargs["is_upsell"], 0)
		mark_paid.assert_not_called()

	def test_fallback_checkout_is_flagged_as_post_purchase_upsell(self):
		from lms.lms.ceu_stripe_webhooks import handle_checkout_completed

		data = {
			"id": "cs_test_fallback",
			"payment_intent": "pi_fallback",
			"amount_total": 2450,
			"currency": "usd",
			"metadata": {
				"type": "one_off",
				"course": "related-course",
				"user": "test@test.com",
				"is_upsell": "1",
				"upsell_type": ceu_upsell.POST_PURCHASE,
				"parent_session": "cs_test_parent",
			},
		}
		with patch("lms.lms.ceu_stripe_webhooks._create_one_off_enrollment", return_value="PAY-2") as enroll, \
			patch("lms.lms.ceu_upsell.mark_offer_paid") as mark_paid:
			handle_checkout_completed(data)

		kwargs = enroll.call_args.kwargs
		self.assertEqual(kwargs["is_upsell"], 1)
		self.assertEqual(kwargs["upsell_type"], ceu_upsell.POST_PURCHASE)
		self.assertEqual(kwargs["parent_session_id"], "cs_test_parent")
		mark_paid.assert_called_once_with(
			"cs_test_parent", ceu_upsell.POST_PURCHASE, payment_name="PAY-2", payment_intent_id="pi_fallback"
		)

	def test_enrollment_is_idempotent_per_session_and_course(self):
		from lms.lms.ceu_stripe_webhooks import _create_one_off_enrollment

		def exists(doctype, filters):
			# Course "a" was already paid for on this session; "b" was not.
			return doctype == "LMS Payment" and filters.get("payment_for_document") == "a"

		# now_datetime() reads System Settings through frappe.get_doc, which is
		# mocked here, so stub it too or the mock gets pickled into the cache.
		with patch("lms.lms.ceu_stripe_webhooks.frappe.db.exists", side_effect=exists), \
			patch("lms.lms.ceu_stripe_webhooks.frappe.get_doc") as get_doc, \
			patch("lms.lms.ceu_stripe_webhooks.now_datetime", return_value="2026-10-07 00:00:00"), \
			patch("lms.lms.ceu_stripe_webhooks.frappe.db.get_value", return_value="Test User"), \
			patch("lms.lms.ceu_enrollment.send_enrollment_confirmation_email"):
			get_doc.return_value.insert.return_value = get_doc.return_value
			get_doc.return_value.name = "PAY-NEW"

			self.assertIsNone(_create_one_off_enrollment(course="a", user="test@test.com", stripe_session_id="cs_1"))
			get_doc.assert_not_called()

			name = _create_one_off_enrollment(course="b", user="test@test.com", stripe_session_id="cs_1", amount_total=2450)
			self.assertEqual(name, "PAY-NEW")
			payment_doc = next(c.args[0] for c in get_doc.call_args_list if c.args[0].get("doctype") == "LMS Payment")
			self.assertEqual(payment_doc["amount"], 24.5)
			self.assertEqual(payment_doc["is_upsell"], 0)

	def test_payment_intent_succeeded_ignores_non_upsell(self):
		from lms.lms.ceu_stripe_webhooks import handle_payment_intent_succeeded

		with patch("lms.lms.ceu_stripe_webhooks._create_one_off_enrollment") as enroll:
			handle_payment_intent_succeeded({"id": "pi_x", "metadata": {}})
			handle_payment_intent_succeeded({"id": "pi_y", "metadata": {"type": "something_else"}})
		enroll.assert_not_called()

	def test_payment_intent_succeeded_enrolls_upsell(self):
		from lms.lms.ceu_stripe_webhooks import handle_payment_intent_succeeded

		data = {
			"id": "pi_upsell",
			"amount": 2450,
			"amount_received": 2450,
			"currency": "usd",
			"metadata": {
				"type": "upsell",
				"course": "related-course",
				"user": "test@test.com",
				"parent_session": "cs_test_parent",
			},
		}
		with patch("lms.lms.ceu_stripe_webhooks._create_one_off_enrollment", return_value="PAY-3") as enroll, \
			patch("lms.lms.ceu_stripe_webhooks.frappe.db.get_value", return_value="Charging"), \
			patch("lms.lms.ceu_upsell.mark_offer_paid") as mark_paid:
			handle_payment_intent_succeeded(data)

		kwargs = enroll.call_args.kwargs
		self.assertEqual(kwargs["course"], "related-course")
		self.assertEqual(kwargs["stripe_payment_intent_id"], "pi_upsell")
		self.assertEqual(kwargs["amount_total"], 2450)
		self.assertEqual(kwargs["is_upsell"], 1)
		self.assertEqual(kwargs["upsell_type"], ceu_upsell.POST_PURCHASE)
		mark_paid.assert_called_once()


class TestAcceptUpsell(UnitTestCase):
	def _run(self, session=None, locked=None, upsell="related-course", settings=SETTINGS_POST,
			intent=None, create_side_effect=None):
		s = MagicMock()
		s.checkout.Session.retrieve.return_value = session or _mock_session()
		if create_side_effect:
			s.PaymentIntent.create.side_effect = create_side_effect
		else:
			s.PaymentIntent.create.return_value = intent or _mock_intent()
		fallback = MagicMock()
		fallback.id = "cs_test_fallback"
		fallback.url = "https://checkout.stripe.com/fallback"
		s.checkout.Session.create.return_value = fallback

		frappe.set_user("test@test.com")
		try:
			with patch("lms.lms.ceu_upsell._stripe", return_value=s), \
				patch("lms.lms.ceu_upsell.get_upsell_settings", return_value=settings), \
				patch("lms.lms.ceu_upsell.frappe.db.get_value", return_value=locked), \
				patch("lms.lms.ceu_upsell.frappe.db.set_value"), \
				patch("lms.lms.ceu_upsell.get_upsell_course", return_value=upsell) as select, \
				patch("lms.lms.ceu_upsell.describe_offer", return_value=dict(OFFER)), \
				patch("lms.lms.ceu_upsell.record_offer"), \
				patch("lms.lms.ceu_stripe_webhooks._create_one_off_enrollment", return_value="PAY-U") as enroll:
				result = ceu_upsell.accept_upsell("cs_test_parent")
				return result, s, enroll, select
		finally:
			frappe.set_user("Administrator")

	def test_happy_path_charges_saved_card_and_enrolls(self):
		result, s, enroll, _ = self._run()
		self.assertEqual(result, {"status": "enrolled", "course": "related-course"})
		kwargs = s.PaymentIntent.create.call_args.kwargs
		self.assertEqual(kwargs["amount"], 2450)
		self.assertEqual(kwargs["customer"], "cus_123")
		self.assertEqual(kwargs["payment_method"], "pm_card")
		self.assertTrue(kwargs["off_session"])
		self.assertTrue(kwargs["confirm"])
		self.assertEqual(kwargs["idempotency_key"], "upsell_cs_test_parent_related-course")
		self.assertEqual(kwargs["metadata"]["type"], "upsell")
		self.assertEqual(kwargs["metadata"]["parent_session"], "cs_test_parent")
		enroll.assert_called_once()
		self.assertEqual(enroll.call_args.kwargs["stripe_payment_intent_id"], "pi_upsell")
		self.assertEqual(enroll.call_args.kwargs["amount_total"], 2450)
		self.assertEqual(enroll.call_args.kwargs["is_upsell"], 1)
		s.checkout.Session.create.assert_not_called()

	def test_second_click_after_payment_charges_nothing(self):
		locked = frappe._dict(status="Paid", upsell_course="related-course")
		result, s, enroll, _ = self._run(locked=locked)
		self.assertEqual(result, {"status": "enrolled", "course": "related-course"})
		s.PaymentIntent.create.assert_not_called()
		enroll.assert_not_called()

	def test_already_enrolled_charges_nothing(self):
		result, s, enroll, _ = self._run(upsell=None)
		self.assertEqual(result, {"status": "already_enrolled"})
		s.PaymentIntent.create.assert_not_called()

	def test_taken_bump_is_excluded_from_post_purchase(self):
		session = _mock_session()
		session["metadata"]["upsell_course"] = "related-course"
		_, _, _, select = self._run(session=session, upsell=None)
		self.assertEqual(select.call_args.kwargs["exclude"], {"main-course", "related-course"})

	def test_card_error_falls_back_to_checkout(self):
		err = stripe.error.CardError("Authentication required", "payment_method", "authentication_required")
		result, s, enroll, _ = self._run(create_side_effect=err)
		self.assertEqual(result["status"], "checkout")
		self.assertEqual(result["url"], "https://checkout.stripe.com/fallback")
		enroll.assert_not_called()
		kwargs = s.checkout.Session.create.call_args.kwargs
		self.assertEqual(kwargs["line_items"][0]["price_data"]["unit_amount"], 2450)
		self.assertEqual(kwargs["metadata"]["type"], "one_off")
		self.assertEqual(kwargs["metadata"]["is_upsell"], "1")
		self.assertEqual(kwargs["metadata"]["parent_session"], "cs_test_parent")
		self.assertEqual(kwargs["metadata"]["course"], "related-course")

	def test_requires_action_is_cancelled_and_falls_back(self):
		result, s, enroll, _ = self._run(intent=_mock_intent(status="requires_action"))
		self.assertEqual(result["status"], "checkout")
		s.PaymentIntent.cancel.assert_called_once_with("pi_upsell")
		enroll.assert_not_called()

	def test_missing_saved_card_falls_back(self):
		session = _mock_session(payment_intent={"id": "pi_parent", "payment_method": None})
		result, s, _, _ = self._run(session=session)
		self.assertEqual(result["status"], "checkout")
		s.PaymentIntent.create.assert_not_called()

	def test_rejects_another_users_session(self):
		session = _mock_session()
		session["metadata"]["user"] = "someone@else.com"
		with self.assertRaises(frappe.PermissionError):
			self._run(session=session)

	def test_rejects_unpaid_session(self):
		with self.assertRaises(frappe.ValidationError):
			self._run(session=_mock_session(payment_status="unpaid"))

	def test_rejects_when_feature_is_off(self):
		with self.assertRaises(frappe.ValidationError):
			self._run(settings=SETTINGS_OFF)


class TestGetUpsellOffer(UnitTestCase):
	def _run(self, settings=SETTINGS_POST, upsell="related-course", existing=None, enrolled=False):
		s = MagicMock()
		s.checkout.Session.retrieve.return_value = _mock_session()

		def get_value(doctype, name, fields=None, as_dict=False, **kwargs):
			if doctype == "LMS Upsell Offer":
				return existing
			return "Main Course"

		frappe.set_user("test@test.com")
		try:
			with patch("lms.lms.ceu_upsell._stripe", return_value=s), \
				patch("lms.lms.ceu_upsell.get_upsell_settings", return_value=settings), \
				patch("lms.lms.ceu_upsell.frappe.db.get_value", side_effect=get_value), \
				patch("lms.lms.ceu_upsell.frappe.db.exists", return_value=enrolled), \
				patch("lms.lms.ceu_upsell.get_upsell_course", return_value=upsell), \
				patch("lms.lms.ceu_upsell.describe_offer", return_value=dict(OFFER)), \
				patch("lms.lms.ceu_upsell.record_offer") as record_offer:
				return ceu_upsell.get_upsell_offer("cs_test_parent"), record_offer
		finally:
			frappe.set_user("Administrator")

	def test_returns_offer_and_records_it_once(self):
		result, record_offer = self._run()
		self.assertEqual(result["status"], "offered")
		self.assertEqual(result["offer"]["course"], "related-course")
		self.assertEqual(result["offer"]["offer_price_cents"], 2450)
		self.assertEqual(result["original_course"], "main-course")
		self.assertFalse(result["original_enrolled"])
		record_offer.assert_called_once()
		self.assertEqual(record_offer.call_args.kwargs["status"], "Offered")

	def test_existing_row_is_not_recorded_again(self):
		existing = frappe._dict(status="Offered", upsell_course="related-course")
		result, record_offer = self._run(existing=existing, enrolled=True)
		self.assertEqual(result["status"], "offered")
		self.assertTrue(result["original_enrolled"])
		record_offer.assert_not_called()

	def test_paid_row_reports_enrolled(self):
		existing = frappe._dict(status="Paid", upsell_course="related-course")
		result, _ = self._run(existing=existing)
		self.assertEqual(result["status"], "enrolled")
		self.assertEqual(result["course"], "related-course")

	def test_no_offer_when_flag_off_or_nothing_to_sell(self):
		result, record_offer = self._run(settings=SETTINGS_OFF)
		self.assertIsNone(result["offer"])
		record_offer.assert_not_called()

		result, record_offer = self._run(upsell=None)
		self.assertIsNone(result["offer"])
		record_offer.assert_not_called()


class TestCustomer(UnitTestCase):
	def test_reuses_stored_customer_without_calling_stripe(self):
		s = MagicMock()
		with patch("lms.lms.ceu_upsell.frappe.db.get_value", return_value="cus_stored"), \
			patch("lms.lms.ceu_upsell.frappe.db.set_value"):
			self.assertEqual(ceu_upsell.find_or_create_customer(s, "test@test.com"), "cus_stored")
		s.Customer.create.assert_not_called()
		s.Customer.list.assert_not_called()

	def test_creates_customer_when_none_exists_anywhere(self):
		s = MagicMock()
		s.Customer.list.return_value = {"data": []}
		s.Customer.create.return_value.id = "cus_new"

		def get_value(doctype, name, field, **kwargs):
			return "Test User" if field == "full_name" else None

		with patch("lms.lms.ceu_upsell.frappe.db.get_value", side_effect=get_value), \
			patch("lms.lms.ceu_upsell.frappe.db.set_value") as set_value:
			self.assertEqual(ceu_upsell.find_or_create_customer(s, "test@test.com"), "cus_new")
		s.Customer.create.assert_called_once()
		self.assertEqual(s.Customer.create.call_args.kwargs["email"], "test@test.com")
		set_value.assert_called_once_with("User", "test@test.com", "stripe_customer_id", "cus_new", update_modified=False)

	def test_missing_customer_error_is_recognised(self):
		err = stripe.error.InvalidRequestError("No such customer: 'cus_x'", "customer")
		self.assertTrue(ceu_upsell.is_missing_customer_error(err))
		self.assertFalse(ceu_upsell.is_missing_customer_error(ValueError("nope")))
		other = stripe.error.InvalidRequestError("Invalid currency", "currency")
		self.assertFalse(ceu_upsell.is_missing_customer_error(other))

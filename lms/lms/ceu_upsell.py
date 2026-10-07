"""Course upsells on one-off purchases.

Two offers, each behind its own flag on CEU Stripe Settings:

* Order bump: a checkbox next to "Buy this course" that adds the course's
  first eligible Related Course to the same Stripe Checkout at a discount.
* Post-purchase: after paying, the buyer lands on /lms/upsell and can add
  the related course with one click, charged off-session to the card Stripe
  saved during the first checkout. If the card can't be charged off-session
  (3DS, decline) they get a normal Checkout for the discounted course instead.

The upsell course is always the first Related Course the buyer can actually
buy (published, paid, priced, not already enrolled). Admins pick upsells by
ordering Related Courses on the course; there is no separate config.

Prices are computed here, server-side, every time. The client never sends a
price. Every offer is recorded as an `LMS Upsell Offer` row, which doubles as
the lock that prevents a double charge on the post-purchase offer.
"""

from decimal import ROUND_HALF_UP, Decimal

import frappe
import stripe
from frappe import _
from frappe.utils import cint, flt

from lms.lms.traffic_source import traffic_fields_from_metadata

ORDER_BUMP = "Order Bump"
POST_PURCHASE = "Post Purchase"

# Stripe rejects card charges under $0.50. Below that there is no offer.
MIN_CHARGE_CENTS = 50
DEFAULT_DISCOUNT_PCT = 50

SAVE_CARD_CONSENT = "Your card will be securely saved for faster future purchases."


# ---------------------------------------------------------------------------
# settings + selection
# ---------------------------------------------------------------------------


def get_upsell_settings() -> dict:
	"""Feature flags and discount from CEU Stripe Settings. Both flags off means
	the checkout flow is exactly what it was before upsells existed."""
	settings = frappe.get_single("CEU Stripe Settings")
	pct = settings.get("upsell_discount_pct")
	pct = DEFAULT_DISCOUNT_PCT if pct is None else cint(pct)
	pct = max(0, min(100, pct))
	return {
		"order_bump": bool(cint(settings.get("enable_order_bump"))),
		"post_purchase": bool(cint(settings.get("enable_post_purchase_upsell"))),
		"discount_pct": pct,
	}


def upsell_price_cents(amount_usd, discount_pct) -> int:
	"""Discounted price in cents, rounded half-up to the cent, never negative.

	Decimal, not float: 19.99 * 100 * 0.5 is 999.49999... in binary floating
	point and would round to 999 instead of 1000.
	"""
	list_cents = (Decimal(str(flt(amount_usd))) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
	pct = max(0, min(100, cint(discount_pct)))
	cents = (list_cents * (100 - pct) / 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
	return max(0, int(cents))


def get_upsell_course(course_name, user, discount_pct=None, exclude=None):
	"""The first Related Course `user` could buy right now, or None.

	Skips unpublished, free, unpriced and self-learning-disabled courses, any
	course the user is already enrolled in, anything in `exclude`, and courses
	whose discounted price falls under Stripe's minimum charge. PPT staff never
	pay, so they never get an offer.
	"""
	if not course_name or not user or user == "Guest":
		return None

	from lms.lms.api import _is_ppt_employee_email

	if _is_ppt_employee_email(user):
		return None

	if discount_pct is None:
		discount_pct = get_upsell_settings()["discount_pct"]
	exclude = set(exclude or ())

	related = frappe.get_all(
		"Related Courses",
		filters={"parent": course_name, "parenttype": "LMS Course"},
		order_by="idx",
		pluck="course",
	)
	for candidate in related:
		if not candidate or candidate == course_name or candidate in exclude:
			continue
		course = frappe.db.get_value(
			"LMS Course",
			candidate,
			["published", "paid_course", "amount_usd", "disable_self_learning"],
			as_dict=True,
		)
		if not course or not course.published or not course.paid_course:
			continue
		if course.disable_self_learning:
			continue
		if upsell_price_cents(course.amount_usd, discount_pct) < MIN_CHARGE_CENTS:
			continue
		if frappe.db.exists("LMS Enrollment", {"course": candidate, "member": user}):
			continue
		return candidate
	return None


def describe_offer(upsell_course, discount_pct) -> dict:
	"""What the UI shows for an offer. Prices are recomputed from the course."""
	course = frappe.db.get_value(
		"LMS Course",
		upsell_course,
		["name", "title", "image", "short_introduction", "ceu_hours", "amount_usd"],
		as_dict=True,
	)
	cents = upsell_price_cents(course.amount_usd, discount_pct)
	return {
		"course": course.name,
		"title": course.title,
		"image": course.image,
		"short_introduction": course.short_introduction,
		"ceu_hours": course.ceu_hours,
		"list_price_usd": flt(course.amount_usd),
		"offer_price_usd": cents / 100,
		"offer_price_cents": cents,
		"discount_pct": cint(discount_pct),
	}


def offer_key(session_id, upsell_type) -> str:
	suffix = "bump" if upsell_type == ORDER_BUMP else "post"
	return f"{session_id}:{suffix}"


# ---------------------------------------------------------------------------
# offer rows (audit trail + lock)
# ---------------------------------------------------------------------------


def record_offer(session_id, upsell_type, user, original_course, offer, status):
	"""Insert or update the LMS Upsell Offer row for this purchase + type."""
	key = offer_key(session_id, upsell_type)
	values = {
		"status": status,
		"member": user,
		"original_course": original_course,
		"upsell_course": offer["course"],
		"parent_session_id": session_id,
		"list_price": offer["list_price_usd"],
		"offer_price": offer["offer_price_usd"],
		"discount_pct": offer["discount_pct"],
		"currency": "USD",
	}
	if frappe.db.exists("LMS Upsell Offer", key):
		frappe.db.set_value("LMS Upsell Offer", key, values)
		return key
	doc = frappe.get_doc(
		{"doctype": "LMS Upsell Offer", "offer_key": key, "upsell_type": upsell_type, **values}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def mark_offer_paid(session_id, upsell_type, payment_name=None, payment_intent_id=None):
	"""Best-effort: the webhook calls this and must never fail over reporting."""
	try:
		key = offer_key(session_id, upsell_type)
		if not frappe.db.exists("LMS Upsell Offer", key):
			return
		values = {"status": "Paid"}
		if payment_name:
			values["payment"] = payment_name
		if payment_intent_id:
			values["stripe_payment_intent_id"] = payment_intent_id
		frappe.db.set_value("LMS Upsell Offer", key, values)
	except Exception:
		frappe.log_error(title="Upsell offer status update failed", message=frappe.get_traceback())


# ---------------------------------------------------------------------------
# Stripe customer (the saved card lives on it)
# ---------------------------------------------------------------------------


def find_or_create_customer(s, user) -> str:
	"""Stripe Customer id for `user`, stored on User.stripe_customer_id.

	Reuses the subscription customer when the member has one, then any Stripe
	customer with the same email, and only then creates one. The stored id is
	trusted; `create_one_off_checkout` recovers if it belongs to the other
	Stripe mode (test vs live) by calling `reset_customer` and retrying once.
	"""
	customer_id = frappe.db.get_value("User", user, "stripe_customer_id")
	if customer_id:
		return customer_id

	customer_id = frappe.db.get_value(
		"CEU Membership",
		{"member": user, "stripe_customer_id": ["!=", ""]},
		"stripe_customer_id",
		order_by="creation desc",
	)
	if not customer_id:
		existing = s.Customer.list(email=user, limit=1)
		data = existing.get("data") if isinstance(existing, dict) else getattr(existing, "data", None)
		if data:
			customer_id = data[0].id
	if not customer_id:
		full_name = frappe.db.get_value("User", user, "full_name") or user
		customer = s.Customer.create(email=user, name=full_name, metadata={"user": user})
		customer_id = customer.id

	frappe.db.set_value("User", user, "stripe_customer_id", customer_id, update_modified=False)
	return customer_id


def reset_customer(user):
	frappe.db.set_value("User", user, "stripe_customer_id", None, update_modified=False)


def is_missing_customer_error(exc) -> bool:
	"""Stripe's "No such customer": the stored id is from the other mode or was deleted."""
	if not isinstance(exc, stripe.error.InvalidRequestError):
		return False
	if getattr(exc, "param", None) == "customer":
		return True
	return "No such customer" in str(exc)


# ---------------------------------------------------------------------------
# whitelisted: order bump
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_order_bump(course_name):
	"""The add-on offered next to "Buy this course", or None."""
	if frappe.session.user == "Guest":
		return None
	settings = get_upsell_settings()
	if not settings["order_bump"]:
		return None
	upsell = get_upsell_course(course_name, frappe.session.user, settings["discount_pct"])
	if not upsell:
		return None
	return describe_offer(upsell, settings["discount_pct"])


# ---------------------------------------------------------------------------
# whitelisted: post-purchase offer page
# ---------------------------------------------------------------------------


def _stripe():
	from lms.lms.ceu_stripe import get_stripe

	return get_stripe()


def _load_paid_session(s, session_id, user):
	"""Retrieve the Checkout Session and prove it is this user's paid one-off purchase."""
	if not session_id or not str(session_id).startswith("cs_"):
		frappe.throw(_("Invalid checkout session"), frappe.ValidationError)
	try:
		session = s.checkout.Session.retrieve(session_id, expand=["payment_intent"])
	except stripe.error.InvalidRequestError:
		frappe.throw(_("Invalid checkout session"), frappe.ValidationError)

	metadata = session.get("metadata") or {}
	if metadata.get("type") != "one_off" or metadata.get("user") != user:
		frappe.throw(_("This checkout session does not belong to you"), frappe.PermissionError)
	if session.get("payment_status") != "paid":
		frappe.throw(_("This purchase has not been paid"), frappe.ValidationError)
	return session


def _session_exclusions(session) -> set:
	"""Courses already bought in this session: the main course and a taken bump."""
	metadata = session.get("metadata") or {}
	return {c for c in (metadata.get("course"), metadata.get("upsell_course")) if c}


@frappe.whitelist()
def get_upsell_offer(session_id):
	"""Everything /lms/upsell needs. `offer` is None when there is nothing to sell."""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("You must be logged in"), frappe.AuthenticationError)

	s = _stripe()
	session = _load_paid_session(s, session_id, user)
	metadata = session.get("metadata") or {}
	original = metadata.get("course")

	result = {
		"original_course": original,
		"original_title": frappe.db.get_value("LMS Course", original, "title"),
		"original_enrolled": bool(
			frappe.db.exists("LMS Enrollment", {"course": original, "member": user})
		),
		"offer": None,
		"status": "none",
	}

	settings = get_upsell_settings()
	if not settings["post_purchase"]:
		return result

	key = offer_key(session_id, POST_PURCHASE)
	existing = frappe.db.get_value(
		"LMS Upsell Offer", key, ["status", "upsell_course"], as_dict=True
	)
	if existing and existing.status == "Paid":
		result.update({"status": "enrolled", "course": existing.upsell_course})
		return result

	upsell = get_upsell_course(
		original, user, settings["discount_pct"], exclude=_session_exclusions(session)
	)
	if not upsell:
		return result

	offer = describe_offer(upsell, settings["discount_pct"])
	if not existing:
		record_offer(session_id, POST_PURCHASE, user, original, offer, status="Offered")
	result.update({"offer": offer, "status": "offered"})
	return result


@frappe.whitelist(methods=["POST"])
def decline_upsell(session_id):
	"""Record "No thanks" so the report can show conversion. Never blocks the buyer."""
	user = frappe.session.user
	if user == "Guest":
		return {"status": "ok"}
	key = offer_key(session_id, POST_PURCHASE)
	row = frappe.db.get_value("LMS Upsell Offer", key, ["member", "status"], as_dict=True)
	if row and row.member == user and row.status == "Offered":
		frappe.db.set_value("LMS Upsell Offer", key, "status", "Declined")
	return {"status": "ok"}


@frappe.whitelist(methods=["POST"])
def accept_upsell(session_id):
	"""One-click charge of the saved card for the post-purchase offer.

	Returns one of:
	  {"status": "enrolled", "course": ...}   charged and enrolled
	  {"status": "checkout", "url": ...}      card needs the buyer (3DS/decline): go pay normally
	  {"status": "already_enrolled"}           nothing left to sell

	Double-charge guards, in order: the offer row is read FOR UPDATE so a
	second click waits for the first request to finish and then sees "Paid";
	the Stripe PaymentIntent uses an idempotency key, so a retry after a crash
	gets the original intent back instead of a new charge; enrollment itself
	is idempotent on (payment intent, course). The charge never waits on the
	original course's webhook, which may land after this page.
	"""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("You must be logged in"), frappe.AuthenticationError)

	settings = get_upsell_settings()
	if not settings["post_purchase"]:
		frappe.throw(_("This offer is no longer available"))

	s = _stripe()
	session = _load_paid_session(s, session_id, user)
	metadata = session.get("metadata") or {}
	original = metadata.get("course")
	key = offer_key(session_id, POST_PURCHASE)

	# Lock the offer row for the rest of this request. A concurrent click
	# blocks here until we commit, then reads the final status below. A row
	# left in "Charging" by a request that died mid-charge is safe to retry
	# because of the Stripe idempotency key.
	locked = frappe.db.get_value(
		"LMS Upsell Offer", key, ["status", "upsell_course"], as_dict=True, for_update=True
	)
	if locked and locked.status == "Paid":
		return {"status": "enrolled", "course": locked.upsell_course}

	upsell = get_upsell_course(
		original, user, settings["discount_pct"], exclude=_session_exclusions(session)
	)
	if not upsell:
		return {"status": "already_enrolled"}

	offer = describe_offer(upsell, settings["discount_pct"])
	record_offer(session_id, POST_PURCHASE, user, original, offer, status="Charging")

	payment_intent = session.get("payment_intent")
	payment_method = None
	if payment_intent and not isinstance(payment_intent, str):
		payment_method = payment_intent.get("payment_method")
	customer = session.get("customer")
	if not payment_method or not customer:
		return _fallback_checkout(s, session_id, user, original, offer, reason="no saved card")

	try:
		intent = s.PaymentIntent.create(
			amount=offer["offer_price_cents"],
			currency="usd",
			customer=customer,
			payment_method=payment_method,
			off_session=True,
			confirm=True,
			description=f"{offer['title']} (add-on, {offer['discount_pct']}% off)",
			metadata={
				"type": "upsell",
				"course": upsell,
				"user": user,
				"parent_session": session_id,
				"upsell_type": POST_PURCHASE,
			},
			idempotency_key=f"upsell_{session_id}_{upsell}",
		)
	except stripe.error.CardError as e:
		# authentication_required, card_declined, insufficient_funds, ...
		# Never retry off-session; hand the buyer a normal Checkout instead.
		reason = getattr(e, "code", None) or str(e)
		return _fallback_checkout(s, session_id, user, original, offer, reason=reason)

	if intent.get("status") == "succeeded":
		from lms.lms.ceu_stripe_webhooks import _create_one_off_enrollment

		payment_name = _create_one_off_enrollment(
			course=upsell,
			user=user,
			stripe_payment_intent_id=intent.id,
			amount_total=offer["offer_price_cents"],
			currency="usd",
			traffic=traffic_fields_from_metadata(metadata),
			is_upsell=1,
			upsell_type=POST_PURCHASE,
			parent_session_id=session_id,
		)
		frappe.db.set_value(
			"LMS Upsell Offer",
			key,
			{"status": "Paid", "stripe_payment_intent_id": intent.id, "payment": payment_name},
		)
		return {"status": "enrolled", "course": upsell}

	# requires_action / processing / anything else. Cancel what can be
	# cancelled so no intent confirms later behind the buyer's back.
	try:
		if intent.get("status") in (
			"requires_action",
			"requires_confirmation",
			"requires_payment_method",
		):
			s.PaymentIntent.cancel(intent.id)
	except stripe.error.StripeError:
		pass
	return _fallback_checkout(
		s, session_id, user, original, offer, reason=f"intent {intent.get('status')}"
	)


def _fallback_checkout(s, parent_session_id, user, original_course, offer, reason=None):
	"""Normal Checkout for the discounted upsell course. Same webhook path as any
	one-off purchase; metadata marks it as an upsell for reporting."""
	course = offer["course"]
	product_data = {
		"name": f"{offer['title']} (add-on, {offer['discount_pct']}% off)",
		"metadata": {"course": course},
	}
	if offer.get("ceu_hours"):
		product_data["description"] = f"{offer['ceu_hours']} CEU Hours"

	checkout = s.checkout.Session.create(
		mode="payment",
		customer_email=user,
		line_items=[
			{
				"price_data": {
					"currency": "usd",
					"unit_amount": offer["offer_price_cents"],
					"product_data": product_data,
				},
				"quantity": 1,
			}
		],
		metadata={
			"type": "one_off",
			"course": course,
			"user": user,
			"is_upsell": "1",
			"upsell_type": POST_PURCHASE,
			"parent_session": parent_session_id,
		},
		success_url=frappe.utils.get_url(f"/lms/courses/{course}?payment=success"),
		cancel_url=frappe.utils.get_url(f"/lms/courses/{original_course}?payment=success"),
	)

	frappe.db.set_value(
		"LMS Upsell Offer",
		offer_key(parent_session_id, POST_PURCHASE),
		{"status": "Checkout", "fallback_session_id": checkout.id, "error": reason},
	)
	return {"status": "checkout", "url": checkout.url}

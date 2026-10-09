"""Coupon redemption for Stripe Checkout.

Admins create `LMS Coupon` records (Settings -> Coupons) and attach the courses
and events each code applies to. Buyers enter the code on the course or event
page; the price they see and the price Stripe charges are both computed here,
server-side, from the code and the item. The client never sends a price.

Flow:

* `preview_coupon` validates the code for one item and returns the discounted
  price for display.
* `create_one_off_checkout` / `create_event_checkout` call `apply_coupon` again
  (never trusting the preview), lower the Stripe line item and stash the coupon
  in Checkout metadata.
* The webhook copies the metadata onto `LMS Payment` and bumps the coupon's
  redemption count, once per payment.
* A 100% coupon skips Stripe entirely: the enrollment/registration is created
  right away with a $0 payment record, because Stripe Checkout cannot take a
  zero-amount card payment.

The coupon discounts the item being bought only. An order-bump course added to
the same Checkout keeps its own upsell price.
"""

from decimal import ROUND_HALF_UP, Decimal

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate

# Stripe rejects card charges under $0.50 (same limit ceu_upsell uses).
MIN_CHARGE_CENTS = 50

ITEM_LABELS = {"LMS Course": "course", "LMS Event": "event"}


# --------------------------------------------------------------------------- #
# Item pricing (shared with ceu_stripe so preview and checkout always agree)
# --------------------------------------------------------------------------- #


def course_usd_price(course) -> float:
	"""USD list price of a course doc. 0 when none is configured."""
	return flt(course.amount_usd or 0)


def event_usd_price(event) -> tuple:
	"""(USD price, is_early_bird) for an event doc.

	Stripe is USD-only. If the event is priced in USD, `amount` is
	authoritative; otherwise `amount_usd` is the USD equivalent. The early-bird
	price replaces the list price while today is on or before the deadline.
	"""
	is_usd = (event.currency or "").upper() == "USD"
	if is_usd:
		amount_usd = event.amount_usd or event.amount or 0
	else:
		amount_usd = event.amount_usd or 0

	is_early_bird = False
	if event.early_bird_deadline and getdate(nowdate()) <= getdate(event.early_bird_deadline):
		if is_usd:
			eb = event.early_bird_amount_usd or event.early_bird_amount or 0
		else:
			eb = event.early_bird_amount_usd or 0
		if eb and float(eb) > 0:
			amount_usd = eb
			is_early_bird = True

	return flt(amount_usd), is_early_bird


def item_usd_price(doctype: str, docname: str) -> float:
	"""USD price the buyer would pay right now for a course or event."""
	doc = frappe.get_doc(doctype, docname)
	if doctype == "LMS Course":
		if not doc.paid_course:
			frappe.throw(_("This course is not for sale"))
		return course_usd_price(doc)
	if doctype == "LMS Event":
		if not doc.paid_event:
			frappe.throw(_("This event is not for sale"))
		return event_usd_price(doc)[0]
	frappe.throw(_("Coupons cannot be applied to {0}").format(doctype))


# --------------------------------------------------------------------------- #
# Validation and math
# --------------------------------------------------------------------------- #


def normalize_code(code) -> str:
	return (code or "").strip().upper()


def resolve_coupon(doctype: str, docname: str, code: str) -> dict:
	"""Load and validate the coupon `code` for one item, or throw.

	Checks, in order: exists and enabled, not expired, under its usage limit,
	listed as applicable to (doctype, docname).
	"""
	code = normalize_code(code)
	if not code:
		frappe.throw(_("Please enter a coupon code"))

	if doctype not in ITEM_LABELS:
		frappe.throw(_("Coupons cannot be applied to {0}").format(doctype))

	coupon_name = frappe.db.exists("LMS Coupon", {"code": code, "enabled": 1})
	if not coupon_name:
		frappe.throw(_("The coupon code '{0}' is invalid.").format(code))

	coupon = frappe.db.get_value(
		"LMS Coupon",
		coupon_name,
		[
			"name",
			"code",
			"expires_on",
			"usage_limit",
			"redemption_count",
			"discount_type",
			"percentage_discount",
			"fixed_amount_discount",
		],
		as_dict=True,
	)

	if coupon.expires_on and getdate(coupon.expires_on) < getdate(nowdate()):
		frappe.throw(_("This coupon has expired."))

	if coupon.usage_limit and cint(coupon.redemption_count) >= cint(coupon.usage_limit):
		frappe.throw(_("This coupon has reached its maximum usage limit."))

	applicable = frappe.db.exists(
		"LMS Coupon Item",
		{
			"parent": coupon.name,
			"parenttype": "LMS Coupon",
			"reference_doctype": doctype,
			"reference_name": docname,
		},
	)
	if not applicable:
		frappe.throw(
			_("This coupon is not applicable to this {0}.").format(_(ITEM_LABELS[doctype]))
		)

	return coupon


def _to_cents(amount_usd) -> int:
	return int(
		(Decimal(str(flt(amount_usd))) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
	)


def discount_cents(original_cents: int, coupon: dict) -> int:
	"""Discount in cents for a coupon on an item priced `original_cents`.

	Percentage: rounded half-up to the cent. Fixed Amount: the configured
	dollar amount, never more than the price. Never negative.
	"""
	original_cents = max(cint(original_cents), 0)
	if coupon.get("discount_type") == "Percentage":
		pct = max(0, min(100, cint(coupon.get("percentage_discount"))))
		cents = int(
			(Decimal(original_cents) * Decimal(pct) / Decimal(100)).quantize(
				Decimal("1"), rounding=ROUND_HALF_UP
			)
		)
	elif coupon.get("discount_type") == "Fixed Amount":
		cents = _to_cents(coupon.get("fixed_amount_discount") or 0)
	else:
		cents = 0
	return max(0, min(cents, original_cents))


def describe_discount(coupon: dict) -> str:
	"""Short human label: '20% off' or '$10 off'."""
	if coupon.get("discount_type") == "Percentage":
		return f"{cint(coupon.get('percentage_discount'))}% off"
	amount = flt(coupon.get("fixed_amount_discount") or 0)
	return f"${amount:,.0f} off" if amount == int(amount) else f"${amount:,.2f} off"


def price_with_coupon(original_usd, coupon: dict) -> dict:
	"""Pricing breakdown for `coupon` applied to an item listed at `original_usd`."""
	original_cents = _to_cents(original_usd)
	off = discount_cents(original_cents, coupon)
	final_cents = original_cents - off
	return {
		"coupon": coupon["name"],
		"code": coupon["code"],
		"discount_type": coupon.get("discount_type"),
		"label": describe_discount(coupon),
		"original_cents": original_cents,
		"discount_cents": off,
		"final_cents": final_cents,
		"original_usd": original_cents / 100,
		"discount_usd": off / 100,
		"final_usd": final_cents / 100,
		"is_free": final_cents == 0,
	}


def apply_coupon(doctype: str, docname: str, code: str, original_usd) -> dict:
	"""Validate `code` for the item and price it. Throws on any problem.

	A discounted total that is above $0 but under Stripe's minimum charge is
	rejected here rather than failing later inside Stripe.
	"""
	coupon = resolve_coupon(doctype, docname, code)
	pricing = price_with_coupon(original_usd, coupon)
	if 0 < pricing["final_cents"] < MIN_CHARGE_CENTS:
		frappe.throw(
			_("This coupon leaves a total under the minimum card charge of $0.50 and cannot be used here.")
		)
	return pricing


# --------------------------------------------------------------------------- #
# Checkout metadata <-> LMS Payment
# --------------------------------------------------------------------------- #


def checkout_metadata(pricing: dict) -> dict:
	"""Stripe Checkout metadata for an applied coupon (values must be strings)."""
	return {
		"coupon": pricing["coupon"],
		"coupon_code": pricing["code"],
		"original_cents": str(pricing["original_cents"]),
		"discount_cents": str(pricing["discount_cents"]),
	}


def payment_fields_from_metadata(metadata) -> dict | None:
	"""LMS Payment fields recorded for the coupon on a Checkout, or None."""
	metadata = metadata or {}
	if not metadata.get("coupon"):
		return None
	return {
		"coupon": metadata.get("coupon"),
		"coupon_code": metadata.get("coupon_code"),
		"original_amount": cint(metadata.get("original_cents")) / 100,
		"discount_amount": cint(metadata.get("discount_cents")) / 100,
	}


def payment_fields_from_pricing(pricing: dict) -> dict:
	return payment_fields_from_metadata(checkout_metadata(pricing))


def record_redemption(coupon_name):
	"""Increment the coupon's redemption count. Callers invoke this once per
	LMS Payment they create, so a replayed webhook never double-counts."""
	if not coupon_name or not frappe.db.exists("LMS Coupon", coupon_name):
		return
	frappe.db.sql(
		"""
		UPDATE `tabLMS Coupon`
		SET redemption_count = COALESCE(redemption_count, 0) + 1
		WHERE name = %s
		""",
		(coupon_name,),
	)


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


@frappe.whitelist()
def preview_coupon(doctype: str, docname: str, code: str) -> dict:
	"""Validate a coupon for a course or event and return the discounted price.

	Display only. Checkout re-validates and re-prices from scratch.
	"""
	if frappe.session.user == "Guest":
		frappe.throw(_("Please log in to apply a coupon"), frappe.AuthenticationError)
	original_usd = item_usd_price(doctype, docname)
	if original_usd <= 0:
		frappe.throw(_("This {0} has no USD price configured").format(_(ITEM_LABELS.get(doctype, "item"))))
	pricing = apply_coupon(doctype, docname, code, original_usd)
	# Internal names stay server-side; the client only needs what it shows.
	return {
		"code": pricing["code"],
		"label": pricing["label"],
		"original_usd": pricing["original_usd"],
		"discount_usd": pricing["discount_usd"],
		"final_usd": pricing["final_usd"],
		"is_free": pricing["is_free"],
	}


def enroll_free_course(course_name: str, user: str, pricing: dict) -> dict:
	"""100%-off path for a course: enroll now, record a $0 payment, no Stripe."""
	from lms.lms.ceu_stripe_webhooks import _create_one_off_enrollment
	from lms.lms.traffic_source import checkout_traffic_metadata, traffic_fields_from_metadata

	if frappe.db.exists("LMS Enrollment", {"course": course_name, "member": user}):
		frappe.throw(_("You are already enrolled in this course"))

	_create_one_off_enrollment(
		course=course_name,
		user=user,
		amount_total=0,
		currency="usd",
		traffic=traffic_fields_from_metadata(checkout_traffic_metadata()),
		coupon=payment_fields_from_pricing(pricing),
	)
	return {"status": "enrolled", "redirect_to": f"/lms/courses/{course_name}"}


def register_free_event(event_name: str, user: str, pricing: dict) -> dict:
	"""100%-off path for an event: register now, record a $0 payment, no Stripe."""
	from lms.lms.ceu_stripe_webhooks import _create_event_registration

	if frappe.db.exists("LMS Event Registration", {"event": event_name, "member": user}):
		frappe.throw(_("You are already registered for this event"))

	_create_event_registration(
		event=event_name,
		user=user,
		amount_total=0,
		currency="usd",
		coupon=payment_fields_from_pricing(pricing),
	)
	return {"status": "enrolled", "redirect_to": f"/lms/events/{event_name}"}

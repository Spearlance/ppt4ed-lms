import frappe
from frappe import _
from frappe.utils import cint, getdate, nowdate
import stripe

from lms.lms.traffic_source import checkout_traffic_metadata


def get_stripe():
    """Initialize Stripe with settings."""
    from lms.lms.doctype.ceu_stripe_settings.ceu_stripe_settings import get_stripe_settings
    settings = get_stripe_settings()
    stripe.api_key = settings["secret_key"]
    return stripe


@frappe.whitelist(allow_guest=True)
def get_stripe_test_mode():
    """Return whether Stripe is in test mode. Safe for guests — exposes no secrets."""
    try:
        return bool(frappe.db.get_single_value("CEU Stripe Settings", "test_mode"))
    except Exception:
        return False


@frappe.whitelist()
def create_one_off_checkout(course_name, add_upsell=0):
    """Create a Stripe Checkout session for a one-off course purchase.

    Price and buyer identity are derived server-side. Never trust client input
    for either — that would let anyone pay $0.01 for any course.

    `add_upsell` is the order-bump checkbox: it only says "yes, add it". Which
    course and at what price is decided here from Related Courses and
    CEU Stripe Settings (see lms/lms/ceu_upsell.py). With both upsell flags
    off this function behaves exactly as it did before upsells existed.
    """
    if frappe.session.user == "Guest":
        frappe.throw(_("You must be logged in to purchase a course"), frappe.AuthenticationError)

    # PPT staff never pay — short-circuit before hitting Stripe so a stale tab
    # or future UI regression can't charge them.
    from lms.lms.api import _is_ppt_employee_email
    if _is_ppt_employee_email(frappe.session.user):
        frappe.throw(_("PPT staff have free access — please refresh the page to enroll."))

    course = frappe.get_doc("LMS Course", course_name)
    if not course.paid_course:
        frappe.throw(_("This course is not for sale"))

    amount_usd = course.amount_usd or 0
    if amount_usd <= 0:
        frappe.throw(_("This course has no USD price configured"))

    user_email = frappe.session.user
    unit_amount_cents = int(round(float(amount_usd) * 100))

    product_data = {"name": course.title, "metadata": {"course": course_name}}
    if course.ceu_hours:
        product_data["description"] = f"{course.ceu_hours} CEU Hours"

    line_items = [{
        "price_data": {
            "currency": "usd",
            "unit_amount": unit_amount_cents,
            "product_data": product_data,
        },
        "quantity": 1
    }]
    metadata = {
        "type": "one_off",
        "course": course_name,
        "user": user_email,
        # The webhook creates the enrollment and has no browser, so the
        # buyer's traffic source rides along here.
        **checkout_traffic_metadata(),
    }
    success_url = frappe.utils.get_url(f"/lms/courses/{course_name}?payment=success")
    buyer = {"customer_email": user_email}

    from lms.lms import ceu_upsell
    settings = ceu_upsell.get_upsell_settings()
    upsell_course = None
    if settings["order_bump"] or settings["post_purchase"]:
        upsell_course = ceu_upsell.get_upsell_course(
            course_name, user_email, settings["discount_pct"]
        )

    s = get_stripe()

    # Order bump: a second line item on the same Checkout. The webhook splits
    # the total using `upsell_cents` from metadata, so the split is whatever
    # the server decided here, never what the client or Stripe reports.
    bump_offer = None
    bump_taken = False
    if upsell_course and settings["order_bump"]:
        bump_offer = ceu_upsell.describe_offer(upsell_course, settings["discount_pct"])
        if cint(add_upsell):
            bump_taken = True
            bump_product = {
                "name": f"{bump_offer['title']} (add-on, {bump_offer['discount_pct']}% off)",
                "metadata": {"course": upsell_course},
            }
            if bump_offer.get("ceu_hours"):
                bump_product["description"] = f"{bump_offer['ceu_hours']} CEU Hours"
            line_items.append({
                "price_data": {
                    "currency": "usd",
                    "unit_amount": bump_offer["offer_price_cents"],
                    "product_data": bump_product,
                },
                "quantity": 1
            })
            metadata["upsell_course"] = upsell_course
            metadata["upsell_cents"] = str(bump_offer["offer_price_cents"])

    # Post-purchase offer: save the card on a Stripe Customer so /lms/upsell
    # can charge it with one click. Only when there is something to offer
    # after this checkout; a taken bump already sold the related course.
    save_card = bool(upsell_course and settings["post_purchase"] and not bump_taken)
    if save_card:
        buyer = {
            "customer": ceu_upsell.find_or_create_customer(s, user_email),
            "payment_intent_data": {"setup_future_usage": "off_session"},
            "custom_text": {"submit": {"message": ceu_upsell.SAVE_CARD_CONSENT}},
        }
        success_url = frappe.utils.get_url("/lms/upsell?session_id={CHECKOUT_SESSION_ID}")

    def _create_session():
        return s.checkout.Session.create(
            mode="payment",
            line_items=line_items,
            metadata=metadata,
            success_url=success_url,
            cancel_url=frappe.utils.get_url(f"/lms/courses/{course_name}?payment=cancelled"),
            **buyer,
        )

    try:
        session = _create_session()
    except stripe.error.InvalidRequestError as e:
        if not (save_card and ceu_upsell.is_missing_customer_error(e)):
            raise
        # The stored customer id belongs to the other Stripe mode (test vs
        # live, e.g. after a dev->prod clone) or was deleted. Mint a fresh
        # one and try exactly once more.
        ceu_upsell.reset_customer(user_email)
        buyer["customer"] = ceu_upsell.find_or_create_customer(s, user_email)
        session = _create_session()

    if bump_offer:
        ceu_upsell.record_offer(
            session.id,
            ceu_upsell.ORDER_BUMP,
            user_email,
            course_name,
            bump_offer,
            status="Accepted" if bump_taken else "Declined",
        )

    return {"url": session.url, "session_id": session.id}


@frappe.whitelist()
def create_event_checkout(event_name):
    """Create a Stripe Checkout session for a paid event registration.

    Price and buyer identity are derived server-side. Never trust client input
    for either — that would let anyone pay $0.01 for any event.
    """
    if frappe.session.user == "Guest":
        frappe.throw(_("You must be logged in to register for an event"), frappe.AuthenticationError)

    from lms.lms.api import _is_ppt_employee_email
    if _is_ppt_employee_email(frappe.session.user):
        frappe.throw(_("PPT staff have free access — please refresh the page to register."))

    event = frappe.get_doc("LMS Event", event_name)
    if not event.paid_event:
        frappe.throw(_("This event is not for sale"))

    # Stripe is USD-only for now. If the event is priced in USD, the `amount`
    # field is authoritative; `amount_usd` is the USD equivalent for non-USD events.
    if (event.currency or "").upper() == "USD":
        amount_usd = event.amount_usd or event.amount or 0
    else:
        amount_usd = event.amount_usd or 0

    # Early-bird auto-discount: when today is on or before the deadline and
    # an early-bird amount exists, swap in the lower price. Selection happens
    # server-side so the client cannot ask for it after the cutoff.
    is_early_bird = False
    if event.early_bird_deadline and getdate(nowdate()) <= getdate(event.early_bird_deadline):
        if (event.currency or "").upper() == "USD":
            eb = event.early_bird_amount_usd or event.early_bird_amount or 0
        else:
            eb = event.early_bird_amount_usd or 0
        if eb and float(eb) > 0:
            amount_usd = eb
            is_early_bird = True

    if amount_usd <= 0:
        frappe.throw(_("This event has no USD price configured"))

    user_email = frappe.session.user

    if frappe.db.exists("LMS Event Registration", {"event": event_name, "member": user_email}):
        frappe.throw(_("You are already registered for this event"))

    # Best-effort seat check; the webhook may still oversell under a race.
    # Accepted risk for v1 — refund manually if it happens.
    if event.seat_count:
        enrolled = frappe.db.count("LMS Event Registration", {"event": event_name})
        if enrolled >= event.seat_count:
            frappe.throw(_("There are no seats available for this event"))

    unit_amount_cents = int(round(float(amount_usd) * 100))

    product_data = {"name": event.title}
    if event.credit_hours:
        product_data["description"] = f"{event.credit_hours} CEU Hours"
    if is_early_bird:
        product_data["description"] = (
            f"{product_data['description']} — Early Bird"
            if product_data.get("description")
            else "Early Bird"
        )

    s = get_stripe()
    session = s.checkout.Session.create(
        mode="payment",
        customer_email=user_email,
        line_items=[{
            "price_data": {
                "currency": "usd",
                "unit_amount": unit_amount_cents,
                "product_data": product_data,
            },
            "quantity": 1
        }],
        metadata={
            "type": "event_one_off",
            "event": event_name,
            "user": user_email,
            "early_bird": "1" if is_early_bird else "0",
        },
        success_url=frappe.utils.get_url(f"/lms/events/{event_name}?payment=success"),
        cancel_url=frappe.utils.get_url(f"/lms/events/{event_name}?payment=cancelled")
    )

    return {"url": session.url, "session_id": session.id}


@frappe.whitelist()
def create_subscription_checkout(plan_name, stripe_price_id, user_email, company_name=None):
    """Create a Stripe Checkout session for a membership subscription."""
    s = get_stripe()

    metadata = {
        "type": "subscription",
        "plan": plan_name,
        "user": user_email
    }
    if company_name:
        metadata["company_name"] = company_name

    session = s.checkout.Session.create(
        mode="subscription",
        customer_email=user_email,
        line_items=[{
            "price": stripe_price_id,
            "quantity": 1
        }],
        metadata=metadata,
        success_url=frappe.utils.get_url("/lms?subscription=success"),
        cancel_url=frappe.utils.get_url("/lms/membership-plans?subscription=cancelled")
    )

    return {"url": session.url, "session_id": session.id}


@frappe.whitelist()
def get_customer_portal_url(membership_name):
    """Get Stripe Customer Portal URL for self-service management."""
    s = get_stripe()
    membership = frappe.get_doc("CEU Membership", membership_name)

    if not membership.stripe_customer_id:
        frappe.throw(_("No Stripe customer linked to this membership"))

    session = s.billing_portal.Session.create(
        customer=membership.stripe_customer_id,
        return_url=frappe.utils.get_url("/lms")
    )

    return {"url": session.url}

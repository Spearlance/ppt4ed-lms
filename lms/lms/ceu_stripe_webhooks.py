import frappe
from frappe import _
from frappe.utils import add_years, cint, today, now_datetime

from lms.lms import ceu_coupon
from lms.lms.traffic_source import traffic_fields_from_metadata


@frappe.whitelist(allow_guest=True, methods=["POST"])
def stripe_webhook():
    """Handle incoming Stripe webhook events."""
    from lms.lms.doctype.ceu_stripe_settings.ceu_stripe_settings import get_stripe_settings
    import stripe

    payload = frappe.request.get_data()
    sig_header = frappe.request.headers.get("Stripe-Signature")
    settings = get_stripe_settings()

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings["webhook_secret"]
        )
    except (ValueError, stripe.error.SignatureVerificationError) as e:
        # frappe.AuthenticationError is not written to Error Log by Frappe's default
        # handler, so log it explicitly before throwing. Record only metadata — never
        # the raw payload, which carries customer + payment identifiers.
        frappe.log_error(
            title="Stripe webhook signature verification failed",
            message=(
                f"exception: {type(e).__name__}: {e}\n"
                f"signature_header_present: {bool(sig_header)}\n"
                f"payload_bytes: {len(payload) if payload else 0}\n"
                f"webhook_secret_configured: {bool(settings.get('webhook_secret'))}\n"
            ),
        )
        frappe.throw(_("Invalid webhook signature"), frappe.AuthenticationError)

    event_type = event["type"]
    event_id = event.get("id")
    data = event["data"]["object"]

    handlers = {
        "checkout.session.completed": handle_checkout_completed,
        "invoice.paid": lambda d: handle_invoice_paid(
            d.get("subscription"),
            invoice_id=d.get("id")
        ),
        "customer.subscription.updated": handle_subscription_updated,
        "customer.subscription.deleted": handle_subscription_deleted,
        "invoice.payment_failed": handle_payment_failed,
        "payment_intent.succeeded": handle_payment_intent_succeeded,
    }

    handler = handlers.get(event_type)
    if not handler:
        return {"status": "ok"}

    try:
        handler(data)
        frappe.db.commit()
    except Exception:
        # Roll back first so the Error Log insert runs on a clean connection —
        # a poisoned transaction (e.g. from a prior "Unknown column" error)
        # would otherwise cause the log insert itself to fail silently.
        frappe.db.rollback()
        frappe.log_error(
            title=f"Stripe webhook handler failed: {event_type}",
            message=f"stripe_event_id: {event_id}\nstripe_event_type: {event_type}\n\n{frappe.get_traceback()}",
        )
        # Re-raise so Stripe sees a 5xx and retries per its backoff schedule.
        raise

    return {"status": "ok"}


def handle_checkout_completed(data):
    """Process successful checkout - one-off purchase or new subscription."""
    metadata = data.get("metadata", {})
    checkout_type = metadata.get("type")

    if checkout_type == "one_off":
        _handle_one_off_checkout(data, metadata)
    elif checkout_type == "event_one_off":
        _handle_event_checkout(data, metadata)
    elif checkout_type == "community_event_donation":
        _confirm_community_event_registration(
            registration=metadata.get("registration"),
            stripe_session_id=data.get("id"),
            stripe_payment_intent_id=data.get("payment_intent"),
            amount_total=data.get("amount_total"),
            currency=data.get("currency"),
        )
    elif checkout_type == "subscription":
        _activate_subscription(
            plan=metadata.get("plan"),
            user=metadata.get("user"),
            stripe_subscription_id=data.get("subscription"),
            stripe_customer_id=data.get("customer"),
            company_name=metadata.get("company_name")
        )


def _handle_one_off_checkout(data, metadata):
    """One-off course purchase, plus the order-bump course when one was added.

    The bump's price rides in metadata (`upsell_cents`) because the server set
    it, so the split needs no extra Stripe call and is stable across replays.
    A fallback Checkout for a post-purchase offer (saved card declined) also
    arrives here, flagged `is_upsell` so the payment reports as an upsell.
    """
    from lms.lms import ceu_upsell

    session_id = data.get("id")
    payment_intent_id = data.get("payment_intent")
    amount_total = cint(data.get("amount_total"))
    upsell_course = metadata.get("upsell_course")
    upsell_cents = cint(metadata.get("upsell_cents")) if upsell_course else 0
    is_upsell = cint(metadata.get("is_upsell"))
    parent_session = metadata.get("parent_session")

    common = {
        "user": metadata.get("user"),
        "stripe_session_id": session_id,
        "stripe_payment_intent_id": payment_intent_id,
        "currency": data.get("currency"),
        "traffic": traffic_fields_from_metadata(metadata),
    }

    main_payment = _create_one_off_enrollment(
        course=metadata.get("course"),
        amount_total=max(amount_total - upsell_cents, 0),
        is_upsell=is_upsell,
        upsell_type=metadata.get("upsell_type") if is_upsell else None,
        parent_session_id=parent_session if is_upsell else None,
        # A coupon discounts the main course only, never the bump add-on.
        coupon=ceu_coupon.payment_fields_from_metadata(metadata),
        **common,
    )
    if is_upsell and parent_session:
        ceu_upsell.mark_offer_paid(
            parent_session,
            metadata.get("upsell_type") or ceu_upsell.POST_PURCHASE,
            payment_name=main_payment,
            payment_intent_id=payment_intent_id,
        )

    if upsell_course:
        bump_payment = _create_one_off_enrollment(
            course=upsell_course,
            amount_total=upsell_cents,
            is_upsell=1,
            upsell_type=ceu_upsell.ORDER_BUMP,
            parent_session_id=session_id,
            **common,
        )
        ceu_upsell.mark_offer_paid(
            session_id,
            ceu_upsell.ORDER_BUMP,
            payment_name=bump_payment,
            payment_intent_id=payment_intent_id,
        )


def _handle_event_checkout(data, metadata):
    """Paid event registration, plus the order-bump course when one was added.

    Same split as course purchases: the event gets the total minus the
    server-set `upsell_cents`, the bump course gets `upsell_cents`.
    """
    session_id = data.get("id")
    payment_intent_id = data.get("payment_intent")
    upsell_course = metadata.get("upsell_course")
    upsell_cents = cint(metadata.get("upsell_cents")) if upsell_course else 0

    _create_event_registration(
        event=metadata.get("event"),
        user=metadata.get("user"),
        stripe_session_id=session_id,
        stripe_payment_intent_id=payment_intent_id,
        amount_total=max(cint(data.get("amount_total")) - upsell_cents, 0),
        currency=data.get("currency"),
        coupon=ceu_coupon.payment_fields_from_metadata(metadata),
    )

    if upsell_course:
        from lms.lms import ceu_upsell

        bump_payment = _create_one_off_enrollment(
            course=upsell_course,
            user=metadata.get("user"),
            stripe_session_id=session_id,
            stripe_payment_intent_id=payment_intent_id,
            amount_total=upsell_cents,
            currency=data.get("currency"),
            is_upsell=1,
            upsell_type=ceu_upsell.ORDER_BUMP,
            parent_session_id=session_id,
        )
        ceu_upsell.mark_offer_paid(
            session_id,
            ceu_upsell.ORDER_BUMP,
            payment_name=bump_payment,
            payment_intent_id=payment_intent_id,
        )


def handle_payment_intent_succeeded(data):
    """Backup path for the one-click post-purchase upsell.

    `accept_upsell` enrolls inside the buyer's request; this catches the case
    where that request died after Stripe had already charged. Every other
    PaymentIntent (Checkout, subscriptions) is ignored here because those
    flows have their own events.
    """
    metadata = data.get("metadata") or {}
    if metadata.get("type") != "upsell":
        return

    from lms.lms import ceu_upsell

    parent_session = metadata.get("parent_session")
    if parent_session:
        # Wait for an in-flight accept_upsell (it holds this row FOR UPDATE)
        # so the enrollment check below sees its result, not a race.
        frappe.db.get_value(
            "LMS Upsell Offer",
            ceu_upsell.offer_key(parent_session, ceu_upsell.POST_PURCHASE),
            "status",
            for_update=True,
        )

    payment_name = _create_one_off_enrollment(
        course=metadata.get("course"),
        user=metadata.get("user"),
        stripe_payment_intent_id=data.get("id"),
        amount_total=data.get("amount_received") or data.get("amount"),
        currency=data.get("currency"),
        is_upsell=1,
        upsell_type=ceu_upsell.POST_PURCHASE,
        parent_session_id=parent_session,
    )
    if parent_session:
        ceu_upsell.mark_offer_paid(
            parent_session,
            ceu_upsell.POST_PURCHASE,
            payment_name=payment_name,
            payment_intent_id=data.get("id"),
        )


def handle_invoice_paid(subscription_id, invoice_id=None):
    """Process successful payment - allocate credits for renewal."""
    if not subscription_id:
        return

    membership = frappe.db.get_value(
        "CEU Membership",
        {"stripe_subscription_id": subscription_id},
        ["name", "plan"],
        as_dict=True
    )

    if not membership:
        return

    plan = frappe.get_doc("CEU Membership Plan", membership.plan)

    from lms.lms.ceu_credits import allocate_credits
    allocate_credits(membership.name, plan.ceu_hours, stripe_invoice_id=invoice_id)

    frappe.db.set_value("CEU Membership", membership.name, "end_date", add_years(today(), 1))

    # Record the dollars. Credit allocation alone left membership revenue
    # invisible to reporting. Fails open inside the helper — a reporting row is
    # never worth failing a payment webhook and triggering a Stripe retry.
    from lms.lms.ceu_transactions import record_invoice_transaction
    record_invoice_transaction(invoice_id, subscription_id=subscription_id)


def handle_subscription_updated(data):
    """Handle plan changes."""
    subscription_id = data.get("id")
    membership_name = frappe.db.get_value(
        "CEU Membership",
        {"stripe_subscription_id": subscription_id},
        "name"
    )
    if not membership_name:
        return


def handle_subscription_deleted(data):
    """Handle cancellation - freeze credit usage and suspend company if applicable."""
    subscription_id = data.get("id")
    membership_name = frappe.db.get_value(
        "CEU Membership",
        {"stripe_subscription_id": subscription_id},
        "name"
    )
    if membership_name:
        frappe.db.set_value("CEU Membership", membership_name, "status", "Cancelled")

        # If this is a company membership, suspend the company
        company_name = frappe.db.get_value(
            "Company Account",
            {"membership": membership_name},
            "name"
        )
        if company_name:
            frappe.db.set_value("Company Account", company_name, "status", "Suspended")


def handle_payment_failed(data):
    """Handle failed payment - set to Past Due."""
    subscription_id = data.get("subscription")
    membership_name = frappe.db.get_value(
        "CEU Membership",
        {"stripe_subscription_id": subscription_id},
        "name"
    )
    if membership_name:
        frappe.db.set_value("CEU Membership", membership_name, "status", "Past Due")


def _create_one_off_enrollment(
    course,
    user,
    stripe_session_id=None,
    stripe_payment_intent_id=None,
    amount_total=None,
    currency=None,
    traffic=None,
    is_upsell=0,
    upsell_type=None,
    parent_session_id=None,
    coupon=None,
):
    """Create an LMS Enrollment for a one-off purchase with ledger entry + billing receipt.

    Idempotent by (checkout session, course), or by (payment intent, course)
    when there is no session (one-click upsell). Stripe may deliver the same
    event more than once, and an order bump puts two courses on one session.

    `traffic` is the buyer's traffic-source fields, carried through Checkout
    metadata because this request comes from Stripe, not from their browser.

    `coupon` is the LMS Payment field dict from ceu_coupon (coupon, coupon_code,
    original_amount, discount_amount). Its redemption is counted here, once
    per payment created, so webhook replays never double-count.

    Returns the LMS Payment name, or None when nothing new was created.
    """
    if stripe_session_id and frappe.db.exists(
        "LMS Payment", {"stripe_session_id": stripe_session_id, "payment_for_document": course}
    ):
        return None
    if not stripe_session_id and stripe_payment_intent_id and frappe.db.exists(
        "LMS Payment",
        {"stripe_payment_intent_id": stripe_payment_intent_id, "payment_for_document": course},
    ):
        return None
    if frappe.db.exists("LMS Enrollment", {"course": course, "member": user}):
        return None

    frappe.get_doc({
        "doctype": "CEU Credit Ledger",
        "user": user,
        "course": course,
        "transaction_type": "Direct Purchase",
        "hours": 0,
        "balance_after": 0,
        "timestamp": now_datetime(),
        "stripe_payment_id": stripe_payment_intent_id,
    }).insert(ignore_permissions=True)

    billing_name = frappe.db.get_value("User", user, "full_name") or user
    amount = (amount_total or 0) / 100
    payment = frappe.get_doc({
        "doctype": "LMS Payment",
        "member": user,
        "billing_name": billing_name,
        "amount": amount,
        "currency": (currency or "usd").upper(),
        "payment_for_document_type": "LMS Course",
        "payment_for_document": course,
        "payment_received": 1,
        "stripe_session_id": stripe_session_id,
        "stripe_payment_intent_id": stripe_payment_intent_id,
        "is_upsell": cint(is_upsell),
        "upsell_type": upsell_type if is_upsell else None,
        "parent_session_id": parent_session_id if is_upsell else None,
        **(coupon or {}),
    }).insert(ignore_permissions=True)
    if coupon:
        ceu_coupon.record_redemption(coupon.get("coupon"))

    frappe.get_doc({
        "doctype": "LMS Enrollment",
        "member": user,
        "course": course,
        "credit_source": "One-Off",
        "payment": payment.name,
        **(traffic or {}),
    }).insert(ignore_permissions=True)

    # Best-effort confirmation/receipt email — the helper fails open so a mail
    # problem can't 500 the webhook and make Stripe re-deliver.
    from lms.lms.ceu_enrollment import send_enrollment_confirmation_email
    send_enrollment_confirmation_email(
        member=user,
        course=course,
        credit_source="One-Off",
        amount=amount,
        currency=(currency or "usd").upper(),
        payment_reference=payment.name,
    )

    return payment.name


def _create_event_registration(
    event,
    user,
    stripe_session_id=None,
    stripe_payment_intent_id=None,
    amount_total=None,
    currency=None,
    coupon=None,
):
    """Create an LMS Event Registration for a paid event with ledger marker + billing receipt.

    Idempotent by stripe_session_id — Stripe may deliver the same event more than once.
    `coupon` is recorded on the payment and counted once, as for courses.

    Returns the LMS Payment name, or None when nothing new was created.
    """
    # Scoped to the event: an order-bump course shares this Checkout Session.
    if stripe_session_id and frappe.db.exists(
        "LMS Payment", {"stripe_session_id": stripe_session_id, "payment_for_document": event}
    ):
        return None
    if frappe.db.exists("LMS Event Registration", {"event": event, "member": user}):
        return None

    # Audit marker — real CEU credits are issued on event completion, not purchase.
    frappe.get_doc({
        "doctype": "CEU Credit Ledger",
        "user": user,
        "transaction_type": "Direct Purchase",
        "hours": 0,
        "balance_after": 0,
        "timestamp": now_datetime(),
        "stripe_payment_id": stripe_payment_intent_id,
        "notes": f"Event purchase: {event}",
    }).insert(ignore_permissions=True)

    billing_name = frappe.db.get_value("User", user, "full_name") or user
    amount = (amount_total or 0) / 100
    payment = frappe.get_doc({
        "doctype": "LMS Payment",
        "member": user,
        "billing_name": billing_name,
        "amount": amount,
        "currency": (currency or "usd").upper(),
        "payment_for_document_type": "LMS Event",
        "payment_for_document": event,
        "payment_received": 1,
        "stripe_session_id": stripe_session_id,
        "stripe_payment_intent_id": stripe_payment_intent_id,
        **(coupon or {}),
    }).insert(ignore_permissions=True)
    if coupon:
        ceu_coupon.record_redemption(coupon.get("coupon"))

    # Impersonate the buyer so LMS Event Registration.validate_owner sees owner == member.
    # Only when this is not already the buyer's own request: frappe.set_user()
    # rewrites session.sid, which inside a logged-in web request (the 100%-coupon
    # path) corrupts the caller's session cookie and logs them out.
    # The registration's legacy validations (validate_payment, validate_self_enrollment,
    # validate_seat_availability, validate_duplicate_members) reference stale field names
    # — those bugs pre-date this PR and are out of scope here.
    registration = {
        "doctype": "LMS Event Registration",
        "event": event,
        "member": user,
        "payment": payment.name,
    }
    original_user = frappe.session.user
    if original_user == user:
        frappe.get_doc(registration).insert(ignore_permissions=True)
    else:
        frappe.set_user(user)
        try:
            frappe.get_doc(registration).insert(ignore_permissions=True)
        finally:
            frappe.set_user(original_user)

    return payment.name


def _confirm_community_event_registration(
    registration,
    stripe_session_id=None,
    stripe_payment_intent_id=None,
    amount_total=None,
    currency=None,
):
    """Mark a Community Event Registration as Confirmed after Stripe Checkout
    succeeds and send the confirmation email.

    Community Events skip the LMS Payment record — that doctype requires a
    User Link and only accepts LMS Course / LMS Event as the dynamic-linked
    document. Community Event registrations are guest-checkout donations, so
    we keep the receipt fields directly on the registration row (stripe ids
    + donation_total) and lean on Stripe's dashboard for full audit.

    Idempotent: if the registration is already Confirmed (e.g. duplicate
    webhook delivery), this no-ops.
    """
    if not registration:
        return

    reg = frappe.db.get_value(
        "Community Event Registration",
        registration,
        ["name", "payment_status"],
        as_dict=True,
    )
    if not reg:
        return
    if reg.payment_status == "Confirmed":
        return

    frappe.db.set_value(
        "Community Event Registration",
        registration,
        {
            "payment_status": "Confirmed",
            "stripe_payment_intent_id": stripe_payment_intent_id,
        },
    )

    from lms.lms.community_event import _send_confirmation_email
    _send_confirmation_email(registration)

    from lms.lms.signup_webhook import queue_signup_webhook
    queue_signup_webhook("Community Event Registration", registration)


def _activate_subscription(plan, user, stripe_subscription_id, stripe_customer_id, company_name=None):
    """Create or activate a CEU Membership."""
    plan_doc = frappe.get_doc("CEU Membership Plan", plan)

    membership = frappe.get_doc({
        "doctype": "CEU Membership",
        "member": user,
        "plan": plan,
        "membership_type": plan_doc.plan_type,
        "stripe_subscription_id": stripe_subscription_id,
        "stripe_customer_id": stripe_customer_id,
        "status": "Active",
        "start_date": today(),
        "end_date": add_years(today(), 1),
        "credit_balance": 0
    }).insert(ignore_permissions=True)

    from lms.lms.ceu_credits import allocate_credits
    allocate_credits(membership.name, plan_doc.ceu_hours)

    # For Company plans, create the Company Account
    if plan_doc.plan_type == "Company":
        _create_company_for_subscription(user, membership.name, company_name)


def _create_company_for_subscription(user, membership_name, company_name=None):
    """Create a Company Account for a new company subscription."""
    if not company_name:
        user_doc = frappe.get_doc("User", user)
        company_name = f"{user_doc.full_name or user}'s Company"

    # Ensure unique company name
    if frappe.db.exists("Company Account", company_name):
        company_name = f"{company_name} ({frappe.utils.now_datetime().strftime('%Y%m%d%H%M')})"

    company = frappe.get_doc({
        "doctype": "Company Account",
        "company_name": company_name,
        "billing_email": user,
        "status": "Active",
        "membership": membership_name,
    }).insert(ignore_permissions=True)

    company.append("admins", {"user": user})
    company.save(ignore_permissions=True)

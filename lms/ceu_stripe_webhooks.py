import frappe
from frappe import _
from frappe.utils import add_years, today


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
    except (ValueError, stripe.error.SignatureVerificationError):
        frappe.throw(_("Invalid webhook signature"), frappe.AuthenticationError)

    event_type = event["type"]
    data = event["data"]["object"]

    handlers = {
        "checkout.session.completed": handle_checkout_completed,
        "invoice.paid": lambda d: handle_invoice_paid(d.get("subscription")),
        "customer.subscription.updated": handle_subscription_updated,
        "customer.subscription.deleted": handle_subscription_deleted,
        "invoice.payment_failed": handle_payment_failed,
    }

    handler = handlers.get(event_type)
    if handler:
        handler(data)
        frappe.db.commit()

    return {"status": "ok"}


def handle_checkout_completed(data):
    """Process successful checkout - one-off purchase or new subscription."""
    metadata = data.get("metadata", {})
    checkout_type = metadata.get("type")

    if checkout_type == "one_off":
        _create_one_off_enrollment(
            course=metadata.get("course"),
            user=metadata.get("user")
        )
    elif checkout_type == "subscription":
        _activate_subscription(
            plan=metadata.get("plan"),
            user=metadata.get("user"),
            stripe_subscription_id=data.get("subscription"),
            stripe_customer_id=data.get("customer")
        )


def handle_invoice_paid(subscription_id):
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
    allocate_credits(membership.name, plan.ceu_hours)

    frappe.db.set_value("CEU Membership", membership.name, "end_date", add_years(today(), 1))


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
    """Handle cancellation - freeze credit usage."""
    subscription_id = data.get("id")
    membership_name = frappe.db.get_value(
        "CEU Membership",
        {"stripe_subscription_id": subscription_id},
        "name"
    )
    if membership_name:
        frappe.db.set_value("CEU Membership", membership_name, "status", "Cancelled")


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


def _create_one_off_enrollment(course, user):
    """Create an LMS Enrollment for a one-off purchase."""
    if frappe.db.exists("LMS Enrollment", {"course": course, "member": user}):
        return
    frappe.get_doc({
        "doctype": "LMS Enrollment",
        "member": user,
        "course": course,
        "credit_source": "One-Off"
    }).insert(ignore_permissions=True)


def _activate_subscription(plan, user, stripe_subscription_id, stripe_customer_id):
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

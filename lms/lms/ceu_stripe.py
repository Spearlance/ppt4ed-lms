import frappe
from frappe import _
import stripe


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
def create_one_off_checkout(course_name, price_amount, user_email):
    """Create a Stripe Checkout session for a one-off course purchase."""
    s = get_stripe()
    course = frappe.get_doc("LMS Course", course_name)

    session = s.checkout.Session.create(
        mode="payment",
        customer_email=user_email,
        line_items=[{
            "price_data": {
                "currency": "usd",
                "unit_amount": int(price_amount),
                "product_data": {
                    "name": course.title,
                    "description": f"{course.ceu_hours} CEU Hours"
                }
            },
            "quantity": 1
        }],
        metadata={
            "type": "one_off",
            "course": course_name,
            "user": user_email
        },
        success_url=frappe.utils.get_url(f"/lms/courses/{course_name}?payment=success"),
        cancel_url=frappe.utils.get_url(f"/lms/courses/{course_name}?payment=cancelled")
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

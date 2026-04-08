import frappe
from frappe.model.document import Document


class CEUStripeSettings(Document):
    pass


def get_stripe_settings():
    """Helper to get Stripe settings as a dict."""
    settings = frappe.get_single("CEU Stripe Settings")
    return {
        "secret_key": settings.get_password("stripe_secret_key"),
        "publishable_key": settings.stripe_publishable_key,
        "webhook_secret": settings.get_password("webhook_secret"),
        "test_mode": settings.test_mode
    }

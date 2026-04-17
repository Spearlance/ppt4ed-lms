import frappe
from frappe.model.document import Document


class CEUStripeSettings(Document):
    pass


def get_stripe_settings():
    """Helper to get Stripe settings as a dict.

    webhook_secret is only used by the webhook verifier; checkout creation
    works without it, so we don't raise if it's unset — otherwise you can't
    register the webhook endpoint in Stripe before the endpoint is functional.
    """
    settings = frappe.get_single("CEU Stripe Settings")
    return {
        "secret_key": settings.get_password("stripe_secret_key"),
        "publishable_key": settings.stripe_publishable_key,
        "webhook_secret": settings.get_password("webhook_secret", raise_exception=False),
        "test_mode": settings.test_mode
    }

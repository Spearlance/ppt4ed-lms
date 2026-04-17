import frappe
from frappe.model.document import Document


RESEND_ACCOUNT_NAME = "Resend"
RESEND_SMTP_SERVER = "smtp.resend.com"
RESEND_SMTP_PORT = 465
RESEND_SMTP_LOGIN = "resend"


class ResendSettings(Document):
    def on_update(self):
        api_key = self.get_password("api_key", raise_exception=False)
        if not api_key or not self.from_email:
            return
        sync_resend_email_account(
            api_key=api_key,
            from_email=self.from_email,
            from_name=self.from_name or "",
            enabled=bool(self.enabled),
        )


def sync_resend_email_account(api_key, from_email, from_name, enabled):
    """Create or update the 'Resend' Email Account to relay via Resend's SMTP."""
    exists = frappe.db.exists("Email Account", RESEND_ACCOUNT_NAME)
    account = frappe.get_doc("Email Account", RESEND_ACCOUNT_NAME) if exists else frappe.new_doc("Email Account")

    if not exists:
        account.email_account_name = RESEND_ACCOUNT_NAME

    account.email_id = from_email
    account.login_id = RESEND_SMTP_LOGIN
    account.password = api_key
    account.smtp_server = RESEND_SMTP_SERVER
    account.smtp_port = RESEND_SMTP_PORT
    account.use_ssl_for_outgoing = 1
    account.enable_outgoing = 1 if enabled else 0
    account.default_outgoing = 1 if enabled else 0
    account.enable_incoming = 0
    account.awaiting_password = 0
    account.sent_items_folder = None
    if from_name:
        account.sender_name = from_name

    account.flags.ignore_mandatory = True
    account.flags.ignore_permissions = True
    account.save()

    if enabled:
        frappe.db.set_value(
            "Email Account",
            {"name": ("!=", RESEND_ACCOUNT_NAME), "default_outgoing": 1},
            "default_outgoing",
            0,
        )


def get_resend_settings():
    """Helper to get Resend settings as a dict."""
    settings = frappe.get_single("Resend Settings")
    return {
        "api_key": settings.get_password("api_key", raise_exception=False),
        "from_email": settings.from_email,
        "from_name": settings.from_name,
        "enabled": bool(settings.enabled),
    }

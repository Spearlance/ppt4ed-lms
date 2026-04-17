import frappe
from frappe.model.document import Document


RESEND_SMTP_SERVER = "smtp.resend.com"
# DigitalOcean blocks outbound 25/465/587 by default; Resend's alt port 2465 (SSL) works.
RESEND_SMTP_PORT = 2465
RESEND_SMTP_LOGIN = "resend"
DEFAULT_ACCOUNT_NAME = "PPT4Ed"


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
    """Create or update the Email Account that relays through Resend's SMTP.

    The account's name (and therefore the From display) tracks `from_name` so
    changing it in Resend Settings renames the Email Account.
    """
    account_name = (from_name or "").strip() or DEFAULT_ACCOUNT_NAME

    # Resend's SMTP login is unique ("resend"), so use it + server to find
    # an existing account even if its name differs from the new account_name.
    existing_name = frappe.db.get_value(
        "Email Account",
        {"smtp_server": RESEND_SMTP_SERVER, "login_id": RESEND_SMTP_LOGIN},
        "name",
    )

    if existing_name and existing_name != account_name:
        frappe.rename_doc("Email Account", existing_name, account_name, force=True)
        existing_name = account_name

    if existing_name:
        account = frappe.get_doc("Email Account", account_name)
    else:
        account = frappe.new_doc("Email Account")
        account.email_account_name = account_name

    account.email_id = from_email
    account.login_id_is_different = 1
    account.login_id = RESEND_SMTP_LOGIN
    account.password = api_key
    account.smtp_server = RESEND_SMTP_SERVER
    account.smtp_port = RESEND_SMTP_PORT
    account.use_ssl_for_outgoing = 1
    account.enable_outgoing = 1 if enabled else 0
    account.default_outgoing = 1 if enabled else 0
    account.enable_incoming = 0
    account.awaiting_password = 0

    account.flags.ignore_mandatory = True
    account.flags.ignore_permissions = True
    account.save()

    if enabled:
        frappe.db.set_value(
            "Email Account",
            {"name": ("!=", account_name), "default_outgoing": 1},
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

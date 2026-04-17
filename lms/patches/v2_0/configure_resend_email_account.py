import frappe


def execute():
    """Seed Resend Settings with sensible defaults and, if the API key is
    present in site_config (`resend_api_key`), activate the Resend Email
    Account so outgoing mail routes through smtp.resend.com.
    """
    settings = frappe.get_single("Resend Settings")

    changed = False
    if not settings.from_email:
        settings.from_email = "noreply@mail.ppt4ed.org"
        changed = True
    if not settings.from_name:
        settings.from_name = "PPT4ed"
        changed = True

    conf_key = frappe.conf.get("resend_api_key")
    if conf_key and not settings.get_password("api_key", raise_exception=False):
        settings.api_key = conf_key
        settings.enabled = 1
        changed = True

    if changed:
        settings.flags.ignore_permissions = True
        settings.save()

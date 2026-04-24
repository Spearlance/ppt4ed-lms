import frappe


def execute():
	"""Enable email-OTP 2FA for every user on every login.

	Gating (per frappe/twofactor.py on frappe v15):
	- System Settings `enable_two_factor_auth` must be 1
	- User must hold at least one Role with `two_factor_auth = 1`
	- Administrator always bypasses — intentional, don't lock out bootstrap

	OTP email delivery uses frappe.sendmail() with the default outgoing
	Email Account, which is the PPT4Ed Resend SMTP relay configured in
	configure_resend_email_account.
	"""
	frappe.db.set_single_value("System Settings", "enable_two_factor_auth", 1)
	frappe.db.set_single_value("System Settings", "two_factor_method", "Email")
	frappe.db.set_single_value("System Settings", "otp_issuer_name", "PPT4Ed")

	frappe.db.sql("UPDATE `tabRole` SET two_factor_auth = 1 WHERE disabled = 0")

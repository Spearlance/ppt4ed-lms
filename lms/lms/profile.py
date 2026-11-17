"""Profile editing for members and LMS admins.

The Edit Profile dialog used to save through `frappe.client.set_value`, which
only works on your own User record. PPT admins have no Desk access, so this is
the one place they can fix an instructor's bio, photo, license or signature.

Only the fields the dialog shows can be written. Email, roles, password and
account status are never reachable from here.
"""

import json

import frappe
from frappe import _

from lms.lms.utils import has_moderator_role

MAX_CREDENTIALS_LENGTH = 140

# User fields the Edit Profile dialog may write.
PROFILE_FIELDS = (
	"first_name",
	"last_name",
	"headline",
	"bio",
	"user_image",
	"mobile_no",
	"linkedin",
	"github",
	"twitter",
	"language",
	"license_type",
	"license_state",
	"professional_license_number",
	"signature_text",
	"credentials",
	"notification_audience",
)

# Built-in accounts are only editable by themselves.
PROTECTED_USERS = ("Administrator", "Guest")


def can_edit_profile(user: str) -> bool:
	if frappe.session.user == "Guest":
		return False
	if frappe.session.user == user:
		return True
	if user in PROTECTED_USERS:
		return False
	return has_moderator_role()


def _clean(value):
	if value is None:
		return ""
	if not isinstance(value, str):
		frappe.throw(_("Profile values must be text."))
	return value.strip()


@frappe.whitelist(methods=["POST"])
def update_profile(user: str, fields: dict | str) -> dict:
	"""Save Edit Profile changes for `user`: yourself, or anyone if you are an
	LMS admin. Returns the saved values."""
	if isinstance(fields, str):
		fields = json.loads(fields)
	if not isinstance(fields, dict) or not fields:
		frappe.throw(_("Nothing to save."))

	if not can_edit_profile(user):
		frappe.throw(_("You cannot edit this profile."), frappe.PermissionError)
	if not frappe.db.exists("User", user):
		frappe.throw(_("User {0} not found.").format(user), frappe.DoesNotExistError)

	unknown = sorted(set(fields) - set(PROFILE_FIELDS))
	if unknown:
		frappe.throw(_("These fields cannot be edited here: {0}").format(", ".join(unknown)))

	values = {key: _clean(value) for key, value in fields.items()}

	for key, label in (("first_name", _("First Name")), ("last_name", _("Last Name"))):
		if key in values and not values[key]:
			frappe.throw(_("{0} is required.").format(label))
	if len(values.get("credentials", "")) > MAX_CREDENTIALS_LENGTH:
		frappe.throw(_("Credentials can be at most {0} characters.").format(MAX_CREDENTIALS_LENGTH))
	for key in ("user_image", "language"):
		# Link / Attach fields store NULL, not an empty string.
		if key in values and not values[key]:
			values[key] = None

	doc = frappe.get_doc("User", user)
	doc.update(values)
	# The role gate above is the permission check; Moderators and Global
	# Admins have no write permission on User.
	doc.save(ignore_permissions=True)

	return {key: doc.get(key) for key in ("name", "full_name", *PROFILE_FIELDS)}

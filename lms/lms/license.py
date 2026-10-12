"""Professional license collection and gating.

The CEU broker cannot award credit without the learner's license type, state
and number, and the three fields on User were optional everywhere, so the
attendee export for a paid event came back blank (investigated 2026-10-12:
0 of 13 paying registrants had a license on file).

Two rules now hold:

1. Public signup whose target is CEU-bearing (any event, a paid or CEU-hour
   course, a membership purchase) collects all three fields up front.
2. Every logged-in entry point that creates a CEU-bearing registration or
   enrollment calls `require_complete_license` first.

Free resources and the bare /lms/signup page stay name/email/password: those
are lead-gen paths and many of those visitors hold no license. The banner in
the app (LicenseBanner.vue) nags them afterwards.
"""

import frappe
from frappe import _

LICENSE_TYPES = ("OT", "PT", "SLP", "Other")
LICENSE_FIELDS = ("license_type", "license_state", "professional_license_number")


class LicenseRequiredError(frappe.ValidationError):
	"""Raised when a CEU-bearing action is attempted without a complete license.

	Its name travels to the browser as `exc_type`, which lets the Vue overlays
	open the license dialog instead of showing a generic toast."""


def missing_license_message():
	return _(
		"Please add your professional license (type, state and number) to your profile "
		"before continuing. PPT cannot award CEU credit without it."
	)


def normalize_license(license_type, license_state, professional_license_number):
	"""Trim and validate the three fields. Throws when any is missing.

	State is upper-cased and capped at 10 chars (matches lms.lms.user.sign_up).
	Type must be one of LICENSE_TYPES; 'Other' is allowed but still needs a
	state and number, since the broker needs something to report."""
	ltype = (license_type or "").strip()
	state = (license_state or "").strip().upper()[:10]
	number = (professional_license_number or "").strip()[:140]

	missing = []
	if not ltype:
		missing.append(_("license type"))
	if not state:
		missing.append(_("license state"))
	if not number:
		missing.append(_("license number"))
	if missing:
		frappe.throw(
			_("Please provide your {0}. PPT cannot award CEU credit without it.").format(
				", ".join(missing)
			),
			LicenseRequiredError,
		)
	if ltype not in LICENSE_TYPES:
		frappe.throw(_("License type must be one of: {0}.").format(", ".join(LICENSE_TYPES)))

	return {
		"license_type": ltype,
		"license_state": state,
		"professional_license_number": number,
	}


def license_required_for_target(target_type, target_slug=None):
	"""Does signing up for / registering on this target need a license?

	Events: always (every event is a CEU event).
	Courses: when paid or carrying CEU hours. Resources never.
	"""
	if target_type == "event":
		return True
	if target_type == "course" and target_slug:
		row = frappe.db.get_value(
			"LMS Course",
			target_slug,
			["paid_course", "ceu_hours", "course_type"],
			as_dict=True,
		)
		if not row or row.course_type == "Resource":
			return False
		return bool(row.paid_course) or (row.ceu_hours or 0) > 0
	return False


def license_required_for_intent(intent):
	"""Membership purchases buy CEU credits, so they need a license too."""
	return bool(intent) and str(intent).startswith("membership:")


def get_license(user=None):
	user = user or frappe.session.user
	if not user or user == "Guest":
		return {}
	row = frappe.db.get_value("User", user, list(LICENSE_FIELDS), as_dict=True) or {}
	return {k: (row.get(k) or "").strip() for k in LICENSE_FIELDS}


def is_license_complete(user=None):
	fields = get_license(user)
	return all(fields.get(k) for k in LICENSE_FIELDS)


def require_complete_license(user=None):
	"""Throw LicenseRequiredError unless the user has all three fields."""
	if not is_license_complete(user):
		frappe.throw(missing_license_message(), LicenseRequiredError)


@frappe.whitelist(methods=["POST"])
def save_my_license(license_type, license_state, professional_license_number):
	"""Write the current user's license onto their own User row.

	Used by the in-app banner and the pre-checkout dialog. Validation lives in
	normalize_license so the stored shape matches what signup writes."""
	if frappe.session.user == "Guest":
		frappe.throw(_("Please log in first."), frappe.AuthenticationError)
	fields = normalize_license(license_type, license_state, professional_license_number)
	frappe.db.set_value("User", frappe.session.user, fields)
	return {**fields, "license_complete": True}

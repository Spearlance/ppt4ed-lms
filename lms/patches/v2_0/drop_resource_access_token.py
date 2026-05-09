"""Drop the `Resource Access Token` doctype.

Replaced by the standard register modal on `/r/<slug>`, which runs the same
signup flow as `/c/<slug>` and `/e/<slug>` (`signup_and_enroll` →
auto-enrollment in the resource on success). The magic-link path is gone:
one signup flow, less code, no separate token lifecycle to maintain.

Idempotent: skipped if the doctype no longer exists.
"""

import frappe


def execute():
	if not frappe.db.exists("DocType", "Resource Access Token"):
		return

	# Drop any lingering tokens first so the table goes away cleanly with the
	# doctype. Tokens are short-lived (30-min) and the only consumers are the
	# now-deleted whitelisted endpoints, so there's nothing to migrate.
	frappe.db.delete("Resource Access Token")

	frappe.delete_doc("DocType", "Resource Access Token", ignore_missing=True, force=True)

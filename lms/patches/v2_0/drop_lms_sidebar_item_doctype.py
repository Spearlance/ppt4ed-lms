"""Drop the legacy `LMS Sidebar Item` child doctype.

Replaced by the standalone `LMS Sidebar Link` doctype, which supports
external URLs (Instagram, Facebook, podcasts, etc.) — the previous
flow could only link to internal Frappe Web Page documents.

Idempotent: skipped if the doctype no longer exists.
"""

import frappe


def execute():
	if not frappe.db.exists("DocType", "LMS Sidebar Item"):
		return

	# Drop any existing child rows first so deleting the doctype doesn't
	# leave orphans in the table (the table itself goes away with the doctype).
	frappe.db.delete("LMS Sidebar Item")

	frappe.delete_doc("DocType", "LMS Sidebar Item", ignore_missing=True, force=True)

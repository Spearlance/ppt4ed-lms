import frappe


def execute():
	"""Force-reload the Certificate print format so the new PPT4ed design
	(ornamental frame, dual logo, CE approvals in the footer, license line)
	replaces whatever is in the DB from the upstream Frappe LMS template.

	Standard print formats are loaded on app install but subsequent edits to
	the JSON file don't always re-sync on bench migrate. A hard reload here
	guarantees the deployed environment picks up the new HTML/CSS.
	"""
	frappe.reload_doc("lms", "print_format", "certificate", force=True)

import frappe
from frappe.utils.nestedset import rebuild_tree


def execute():
	"""Initialize LMS Category as a Tree doctype.

	The doctype JSON adds parent_lms_category / lft / rgt / old_parent / is_group.
	bench migrate runs the schema sync; this patch then rebuilds lft/rgt so the
	existing flat categories become a valid (single-level) nested set.
	"""
	if not frappe.db.exists("DocType", "LMS Category"):
		return

	rebuild_tree("LMS Category")

# Copyright (c) 2023, Frappe and contributors
# For license information, please see license.txt

from frappe.utils.nestedset import NestedSet


class LMSCategory(NestedSet):
	nsm_parent_field = "parent_lms_category"

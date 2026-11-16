# Copyright (c) 2026, PPT4Ed and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class LMSEventMaterial(Document):
	def on_trash(self):
		# The attached File is private and only reachable through this
		# record, so it goes when the material goes.
		for file_name in frappe.get_all(
			"File",
			filters={
				"attached_to_doctype": "LMS Event Material",
				"attached_to_name": self.name,
			},
			pluck="name",
		):
			frappe.delete_doc("File", file_name, ignore_permissions=True, force=True)

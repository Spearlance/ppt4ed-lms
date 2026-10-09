import frappe


def execute():
	"""Point coupon applicable-items at LMS Event instead of the retired LMS Batch.

	LMS Coupon Item.reference_doctype is a Select, so the Batch -> Event rename
	patch (which only rewrote Link options and LMS Payment) left any coupon rows
	saying "LMS Batch". Those rows resolve to a doctype that no longer exists.
	"""
	if not frappe.db.table_exists("LMS Coupon Item"):
		return

	frappe.db.sql(
		"""
		UPDATE `tabLMS Coupon Item`
		SET reference_doctype = 'LMS Event'
		WHERE reference_doctype = 'LMS Batch'
		"""
	)

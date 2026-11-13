import frappe

from lms.lms.ceu_receipts import get_purchase_receipt

no_cache = 1
no_sitemap = 1


def get_context(context):
	context.no_cache = 1
	context.no_sitemap = 1
	context.receipt = get_purchase_receipt(frappe.form_dict.get("transaction"))

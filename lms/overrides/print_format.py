import frappe
from frappe.utils.print_format import download_pdf as _frappe_download_pdf


@frappe.whitelist(allow_guest=True)
def download_pdf(
	doctype,
	name,
	format=None,
	doc=None,
	no_letterhead=0,
	language=None,
	letterhead=None,
	pdf_generator=None,
):
	"""Wrapper around Frappe's download_pdf that rescues legacy certificate links.

	Certificate emails sent before the Chrome-PDF migration link straight to
	frappe.utils.print_format.download_pdf WITHOUT pdf_generator=chrome. Frappe's
	download_pdf hard-defaults a missing pdf_generator to "wkhtmltopdf", which
	cannot render the Chrome-only certificate print format and 500s.

	Those links live in already-sent inboxes and can't be edited, so we fix them
	server-side: when an LMS Certificate is requested with no explicit generator,
	fall back to the print format's own pdf_generator (chrome) instead of
	wkhtmltopdf. Every other doctype keeps Frappe's default behaviour untouched.
	"""
	if doctype == "LMS Certificate" and not pdf_generator and format:
		pdf_generator = frappe.db.get_value("Print Format", format, "pdf_generator") or None

	return _frappe_download_pdf(
		doctype,
		name,
		format=format,
		doc=doc,
		no_letterhead=no_letterhead,
		language=language,
		letterhead=letterhead,
		pdf_generator=pdf_generator,
	)

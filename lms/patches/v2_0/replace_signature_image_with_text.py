import frappe


def execute():
	"""Swap User.signature_image (Attach Image) for User.signature_text (Data).

	The cert print format moved from rendering an uploaded signature image to
	rendering the instructor's typed name in a cursive script font. The image
	custom field is no longer referenced anywhere — drop it so it stops showing
	up on the User form and so the schema matches the fixtures file.

	Also force-reloads the certificate print format JSON since standard print
	formats don't always re-sync on bench migrate (same reason
	v2_0.reload_certificate_print_format exists).
	"""
	frappe.delete_doc(
		"Custom Field",
		"User-signature_image",
		ignore_missing=True,
		force=True,
	)

	frappe.reload_doc("lms", "print_format", "certificate", force=True)

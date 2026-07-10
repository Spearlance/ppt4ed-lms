import frappe


def execute():
	"""Publish already-issued certificates so certified members appear on the
	participant directory (get_certification_query filters published == 1).

	Auto-minted course certificates (PR #36) were created without publishing
	them, so the /certified-participants page and its count showed nothing even
	though congratulations emails were going out. Every such certificate was
	minted only after enrollment progress reached 100 — which on a certified
	course requires submitting the final Course Survey — so it is safe to list.

	This mirrors the historical v1_0.publish_certificates intent and is
	idempotent (only flips rows that are still unpublished).
	"""
	unpublished = frappe.get_all(
		"LMS Certificate",
		filters={"published": 0},
		pluck="name",
	)
	for certificate in unpublished:
		frappe.db.set_value(
			"LMS Certificate", certificate, "published", 1, update_modified=False
		)
	frappe.db.commit()

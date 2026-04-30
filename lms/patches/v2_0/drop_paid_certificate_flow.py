import frappe


def execute():
	"""Convert any LMS Course with paid_certificate=1 to enable_certification=1.

	PPT4Ed auto-mints completion certificates (PRs #36-#38). The legacy
	paid_certificate / "buy a cert after instructor evaluation" flow is being
	removed alongside the Razorpay teardown. Any course still flagged as paid
	cert keeps its certification gate by switching to the standard auto-mint
	path so existing learners aren't denied credit.
	"""
	if not frappe.db.has_column("LMS Course", "paid_certificate"):
		return

	frappe.db.sql("""
		UPDATE `tabLMS Course`
		SET enable_certification = 1,
		    paid_certificate = 0
		WHERE paid_certificate = 1
	""")
	frappe.db.commit()

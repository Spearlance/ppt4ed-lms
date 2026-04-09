import frappe


def execute():
	"""Rename LMS Batch → LMS Event and LMS Batch Enrollment → LMS Event Registration.

	Frappe's rename_doc for DocTypes automatically updates:
	- The DocType record name
	- The database table name (tabLMS Batch → tabLMS Event)
	- All Link fields in other doctypes that point to the renamed DocType
	- Dynamic Links referencing the old DocType name

	We handle column renames and data updates manually where needed.
	"""

	# Phase 1: Rename DocTypes (Frappe handles table rename + Link field options)
	if frappe.db.exists("DocType", "LMS Batch"):
		frappe.rename_doc("DocType", "LMS Batch", "LMS Event", force=True)

	if frappe.db.exists("DocType", "LMS Batch Enrollment"):
		frappe.rename_doc(
			"DocType", "LMS Batch Enrollment", "LMS Event Registration", force=True
		)

	# Phase 2: Rename columns that had "batch" in the fieldname
	# These need explicit ALTER TABLE since rename_doc only updates Link options

	# LMS Event Registration: batch → event
	if frappe.db.has_column("LMS Event Registration", "batch"):
		frappe.db.sql(
			"ALTER TABLE `tabLMS Event Registration` CHANGE `batch` `event` varchar(140)"
		)

	# LMS Live Class: batch_name → event_name
	if frappe.db.has_column("LMS Live Class", "batch_name"):
		frappe.db.sql(
			"ALTER TABLE `tabLMS Live Class` CHANGE `batch_name` `event_name` varchar(140)"
		)

	# LMS Certificate: batch_name → event_name
	if frappe.db.has_column("LMS Certificate", "batch_name"):
		frappe.db.sql(
			"ALTER TABLE `tabLMS Certificate` CHANGE `batch_name` `event_name` varchar(140)"
		)

	# LMS Enrollment: batch → event (if column exists)
	if frappe.db.has_column("LMS Enrollment", "batch"):
		frappe.db.sql(
			"ALTER TABLE `tabLMS Enrollment` CHANGE `batch` `event` varchar(140)"
		)

	# LMS Certificate Request: batch → event (if column exists)
	if frappe.db.has_column("LMS Certificate Request", "batch"):
		frappe.db.sql(
			"ALTER TABLE `tabLMS Certificate Request` CHANGE `batch` `event` varchar(140)"
		)

	# Phase 3: Update data in Dynamic Link / Select fields
	# LMS Payment: payment_for_document_type references
	frappe.db.sql("""
		UPDATE `tabLMS Payment`
		SET payment_for_document_type = 'LMS Event'
		WHERE payment_for_document_type = 'LMS Batch'
	""")

	# Phase 4: Update LMS Event internal field names
	# batch_details → event_details, batch_details_raw → event_details_raw
	# paid_batch → paid_event
	if frappe.db.has_column("LMS Event", "batch_details"):
		frappe.db.sql(
			"ALTER TABLE `tabLMS Event` CHANGE `batch_details` `event_details` longtext"
		)
	if frappe.db.has_column("LMS Event", "batch_details_raw"):
		frappe.db.sql(
			"ALTER TABLE `tabLMS Event` CHANGE `batch_details_raw` `event_details_raw` longtext"
		)
	if frappe.db.has_column("LMS Event", "paid_batch"):
		frappe.db.sql(
			"ALTER TABLE `tabLMS Event` CHANGE `paid_batch` `paid_event` tinyint(1)"
		)

	# Phase 5: Remove Batch Evaluator role permissions from renamed doctypes
	# (These roles were deleted in earlier commits)
	frappe.db.sql("""
		DELETE FROM `tabDocPerm`
		WHERE role = 'Batch Evaluator'
	""")
	frappe.db.sql("""
		DELETE FROM `tabCustom DocPerm`
		WHERE role = 'Batch Evaluator'
	""")

	frappe.db.commit()

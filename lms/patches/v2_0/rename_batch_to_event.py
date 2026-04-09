import frappe


def execute():
	"""Rename LMS Batch → LMS Event and LMS Batch Enrollment → LMS Event Registration.

	Since this is a post_model_sync patch, Frappe's model sync may have already
	created the new DocType records from the JSON files. We need to handle both
	cases: (a) old DocType exists and new doesn't, (b) both exist because model
	sync created the new one as an empty table.
	"""

	# Phase 0: Handle model sync creating the new DocType before this patch runs.
	# If both old and new exist, drop the empty auto-created new ones so rename_doc works.
	_clear_auto_created_doctype("LMS Event", "LMS Batch")
	_clear_auto_created_doctype("LMS Event Registration", "LMS Batch Enrollment")

	# Phase 1: Rename DocTypes (Frappe handles table rename + Link field options)
	if frappe.db.exists("DocType", "LMS Batch"):
		frappe.rename_doc("DocType", "LMS Batch", "LMS Event", force=True)

	if frappe.db.exists("DocType", "LMS Batch Enrollment"):
		frappe.rename_doc(
			"DocType", "LMS Batch Enrollment", "LMS Event Registration", force=True
		)

	# Phase 2: Rename columns that had "batch" in the fieldname
	_rename_column("LMS Event Registration", "batch", "event", "varchar(140)")
	_rename_column("LMS Live Class", "batch_name", "event_name", "varchar(140)")
	_rename_column("LMS Certificate", "batch_name", "event_name", "varchar(140)")
	_rename_column("LMS Certificate", "batch_title", "event_title", "varchar(140)")
	_rename_column("LMS Enrollment", "batch", "event", "varchar(140)")
	_rename_column("LMS Enrollment", "enrollment_from_batch", "enrollment_from_event", "varchar(140)")
	_rename_column("LMS Certificate Request", "batch", "event", "varchar(140)")
	_rename_column("LMS Event", "batch_details", "event_details", "longtext")
	_rename_column("LMS Event", "batch_details_raw", "event_details_raw", "longtext")
	_rename_column("LMS Event", "paid_batch", "paid_event", "tinyint(1)")

	# Phase 3: Update data in Dynamic Link / Select fields
	frappe.db.sql("""
		UPDATE `tabLMS Payment`
		SET payment_for_document_type = 'LMS Event'
		WHERE payment_for_document_type = 'LMS Batch'
	""")

	# Phase 4: Remove deleted role permissions
	frappe.db.sql("DELETE FROM `tabDocPerm` WHERE role = 'Batch Evaluator'")
	frappe.db.sql("DELETE FROM `tabCustom DocPerm` WHERE role = 'Batch Evaluator'")
	frappe.db.sql("DELETE FROM `tabDocPerm` WHERE role = 'Course Creator'")
	frappe.db.sql("DELETE FROM `tabCustom DocPerm` WHERE role = 'Course Creator'")

	frappe.db.commit()


def _clear_auto_created_doctype(new_name, old_name):
	"""If model sync created the new DocType but old table still has data, drop the empty new one."""
	old_table = f"tab{old_name}"
	new_table = f"tab{new_name}"

	old_exists = frappe.db.sql(f"SHOW TABLES LIKE '{old_table}'")
	new_exists = frappe.db.sql(f"SHOW TABLES LIKE '{new_table}'")

	if old_exists and new_exists:
		# Both tables exist — model sync created new empty table, old has the data
		frappe.db.sql(f"DROP TABLE IF EXISTS `{new_table}`")
		# Remove the auto-created DocType record so rename_doc can create it
		if frappe.db.exists("DocType", new_name):
			frappe.db.sql("DELETE FROM `tabDocType` WHERE name = %s", new_name)
			# Clean up related records
			frappe.db.sql("DELETE FROM `tabDocField` WHERE parent = %s", new_name)
			frappe.db.sql("DELETE FROM `tabDocPerm` WHERE parent = %s", new_name)
		frappe.db.commit()


def _rename_column(doctype, old_col, new_col, col_type):
	"""Safely rename a column if the old one exists."""
	table = f"tab{doctype}"
	if frappe.db.sql(f"SHOW COLUMNS FROM `{table}` LIKE '{old_col}'"):
		frappe.db.sql(f"ALTER TABLE `{table}` CHANGE `{old_col}` `{new_col}` {col_type}")

import frappe


def execute():
    frappe.db.sql(
        "UPDATE `tabLMS Course` SET course_type = 'Course' WHERE course_type IS NULL OR course_type = ''"
    )

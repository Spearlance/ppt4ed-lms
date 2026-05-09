"""Add `signup_source` + `signup_source_type` custom fields to User.

Captures which entry-point drove a signup. Populated by `signup_and_enroll`
when the modal on `/r/<slug>`, `/c/<slug>`, or `/e/<slug>` posts a fresh
signup. Lets reports answer "which Free Resource pushed the most signups?"
without a separate attribution doctype.

Direct signups (no `target_type`) keep the default 'Direct'.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	create_custom_fields(
		{
			"User": [
				{
					"fieldname": "signup_source_section",
					"label": "Signup Attribution",
					"fieldtype": "Section Break",
					"insert_after": "last_name",
					"collapsible": 1,
				},
				{
					"fieldname": "signup_source_type",
					"label": "Signup Source Type",
					"fieldtype": "Select",
					"options": "Direct\nResource\nCourse\nEvent",
					"default": "Direct",
					"insert_after": "signup_source_section",
					"no_copy": 1,
					"read_only": 1,
				},
				{
					"fieldname": "signup_source",
					"label": "Signup Source",
					"fieldtype": "Data",
					"length": 140,
					"insert_after": "signup_source_type",
					"description": "Doc name (slug) of the resource/course/event the user signed up from.",
					"no_copy": 1,
					"read_only": 1,
				},
			]
		},
		ignore_validate=True,
	)

	# Backfill existing rows so the column isn't NULL — every report can
	# safely group by signup_source_type without a coalesce.
	frappe.db.sql(
		"""
		UPDATE `tabUser`
		SET signup_source_type = 'Direct'
		WHERE signup_source_type IS NULL OR signup_source_type = ''
		"""
	)

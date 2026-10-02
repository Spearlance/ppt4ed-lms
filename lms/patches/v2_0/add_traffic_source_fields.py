"""Add traffic-source custom fields to User and LMS Enrollment.

`signup_source` / `signup_source_type` (see add_user_signup_attribution_fields)
record which landing page a signup happened on. These record how the visitor
reached the site in the first place: UTM tags, an ad click ID, or the referring
site. Populated by lms/lms/traffic_source.py and read by Admin Reports > Sources.

Existing rows are left blank on purpose. The report shows blank as
"Not tracked", which is the truth for anything created before this shipped.
"""

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def _fields(prefix, insert_after, section_fieldname):
	fields = [
		{
			"fieldname": section_fieldname,
			"label": "Traffic Source",
			"fieldtype": "Section Break",
			"insert_after": insert_after,
			"collapsible": 1,
		}
	]
	previous = section_fieldname
	for key, label, description in (
		("source", "Traffic Source", "utm_source, or the referring site. 'direct' when there was neither."),
		("medium", "Traffic Medium", "utm_medium, e.g. email, cpc, social, organic, referral."),
		("campaign", "Traffic Campaign", "utm_campaign."),
		("referrer", "Traffic Referrer", "Hostname of the site the visitor arrived from."),
	):
		fieldname = f"{prefix}{key}"
		fields.append(
			{
				"fieldname": fieldname,
				"label": label,
				"fieldtype": "Data",
				"length": 140,
				"insert_after": previous,
				"description": description,
				"no_copy": 1,
				"read_only": 1,
			}
		)
		previous = fieldname
	return fields


def execute():
	create_custom_fields(
		{
			"User": _fields("signup_traffic_", "signup_source", "signup_traffic_section"),
			"LMS Enrollment": _fields("traffic_", "membership", "traffic_source_section"),
		},
		ignore_validate=True,
	)

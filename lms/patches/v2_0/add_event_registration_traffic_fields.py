"""Add the traffic-source custom fields to LMS Event Registration.

add_traffic_source_fields put them on User and LMS Enrollment; event
registrations were left out, so Admin Reports > Sources could not say which
channel drove an event signup. Same fields, same semantics: populated by
lms/lms/traffic_source.py from the member's own browser, or carried through
Stripe Checkout metadata for paid registrations.
"""

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from lms.patches.v2_0.add_traffic_source_fields import _fields


def execute():
	create_custom_fields(
		{
			"LMS Event Registration": _fields("traffic_", "membership", "traffic_source_section"),
		},
		ignore_validate=True,
	)

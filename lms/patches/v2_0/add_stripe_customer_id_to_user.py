"""Add User.stripe_customer_id for one-off purchases.

Subscriptions already keep their Stripe customer on CEU Membership. One-off
course checkouts never had one: Checkout was created with `customer_email`,
which saves nothing. The post-purchase upsell charges the card Stripe saved
during the first checkout, and a saved card lives on a Customer, so the
buyer needs a stable Customer id across purchases. Populated lazily by
`lms.lms.ceu_upsell.find_or_create_customer`.
"""

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	create_custom_fields(
		{
			"User": [
				{
					"fieldname": "stripe_customer_id",
					"label": "Stripe Customer ID",
					"fieldtype": "Data",
					"length": 140,
					"insert_after": "signup_traffic_referrer",
					"read_only": 1,
					"no_copy": 1,
					"description": "Stripe Customer used for one-off course purchases. Set on first checkout that saves a card.",
				}
			]
		},
		ignore_validate=True,
	)

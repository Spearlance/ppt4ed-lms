# Copyright (c) 2026, PPT4Ed and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class LMSUpsellOffer(Document):
	"""One upsell offer made during a one-off course purchase.

	Written only by `lms.lms.ceu_upsell` and the Stripe webhook. The row is
	both the audit trail for Admin Reports > Upsells and the lock that stops a
	post-purchase offer from being charged twice (see `accept_upsell`).
	"""

	pass

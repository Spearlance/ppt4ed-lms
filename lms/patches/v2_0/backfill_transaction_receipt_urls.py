"""Fill receipt_url on CEU Transaction rows synced before the field existed.

Profile > Purchases links each purchase to its Stripe-hosted receipt. New rows
get the URL from the sync; this backfills history. Queued on the long worker
because it calls Stripe once per row, and a migrate must never block on the
network. Rows it misses are resolved lazily the first time a member views them.
"""

import frappe


def execute():
	if not frappe.db.count("CEU Transaction"):
		return
	try:
		frappe.enqueue(
			"lms.lms.ceu_transactions.backfill_receipt_urls",
			queue="long",
			timeout=1800,
			enqueue_after_commit=True,
		)
	except Exception:
		# No redis during a cold provision; the lazy lookup covers it.
		frappe.log_error(title="Receipt URL backfill not queued", message=frappe.get_traceback())

"""Private, read-only receipts for historical and current Stripe mirrors."""

from decimal import Decimal, InvalidOperation

import frappe
from frappe import _
from frappe.utils import fmt_money, format_datetime

from lms.lms.ceu_reports import _attach_order_lines
from lms.lms.ceu_transactions import _item_title, _member_for_email, _require_admin

PAID_STATUSES = ("Succeeded", "Partially Refunded", "Refunded")


def _require_login():
	user = frappe.session.user
	if not user or user == "Guest":
		frappe.throw(_("Please log in to view receipts"), frappe.PermissionError)
	return user


def _owns_transaction(row, user):
	# A linked buyer takes precedence over a different payer/billing email.
	return row.get("member") == user if row.get("member") else row.get("customer_email") == user


def _money(value):
	try:
		amount = Decimal(str(value))
	except (InvalidOperation, TypeError, ValueError):
		frappe.throw(_("Receipt amounts are unavailable"), frappe.ValidationError)
	if not amount.is_finite() or amount < 0:
		frappe.throw(_("Receipt amounts are unavailable"), frappe.ValidationError)
	return amount


def get_purchase_receipt(transaction):
	"""Authorize before reading names/lines; never fetch Stripe or write records.

	Not whitelisted: the authenticated www controller is the only entry point.
	CEU Transaction's synced amounts, not catalog prices, are the payment record.
	"""
	user = _require_login()
	if not isinstance(transaction, str) or not transaction:
		frappe.throw(_("Receipt not available"), frappe.PermissionError)
	row = frappe.db.get_value("CEU Transaction", transaction, "*", as_dict=True)
	if not row:
		frappe.throw(_("Receipt not available"), frappe.PermissionError)
	if not _owns_transaction(row, user):
		_require_admin()
	if row.status not in PAID_STATUSES:
		frappe.throw(_("Receipt not available"), frappe.PermissionError)

	buyer = row.get("member") or _member_for_email(row.get("customer_email"))
	profile = (
		frappe.db.get_value(
			"User", buyer, ["first_name", "middle_name", "last_name", "full_name"], as_dict=True
		)
		if buyer
		else None
	)
	# Build from every name component, not get_full_name's email/first-name fallback.
	full_name = " ".join(
		str(profile.get(field) or "").strip()
		for field in ("first_name", "middle_name", "last_name")
		if profile and profile.get(field)
	).strip()
	full_name = full_name or (profile or {}).get("full_name") or row.get("member_full_name")

	gross = _money(row.gross_amount)
	refunded = _money(row.refunded_amount)
	if refunded > gross or not row.get("currency") or not row.get("transaction_date"):
		frappe.throw(_("Receipt amounts are unavailable"), frappe.ValidationError)
	currency = row.currency.upper()

	def display(amount):
		return fmt_money(amount, currency=currency)

	_attach_order_lines([row])
	lines = row.get("line_items") or []
	# LMS Payment amounts can predate a coupon. Never allocate a discount or
	# label catalog/list amounts as paid when they don't reconcile to the charge.
	reconciled = bool(lines) and all(
		line.get("amount") is not None and (line.get("currency") or "").upper() == currency for line in lines
	)
	if reconciled:
		reconciled = sum((_money(line["amount"]) for line in lines), Decimal(0)) == gross
	if not lines:
		lines = [
			{
				"title": row.get("item_title")
				or _item_title(row.get("item_type"), row.get("item"))
				or row.get("description")
				or row.get("transaction_type")
				or _("Purchase"),
				"is_upsell": False,
			}
		]
		# A legacy row describes the purchase but cannot prove item-level allocation.

	return {
		"buyer_name": full_name or _("Name not recorded"),
		"name_missing": not full_name,
		"provider": "PPT4Ed",
		"reference": row.name,
		"purchase_date": format_datetime(row.transaction_date, "MMM d, yyyy h:mm a"),
		"currency": currency,
		"status": _("Refunded")
		if refunded == gross and refunded > 0
		else (_("Partially Refunded") if refunded > 0 else _("Paid")),
		"lines": [
			{
				"title": line["title"],
				"is_upsell": bool(line.get("is_upsell")),
				"amount_display": display(_money(line["amount"])) if reconciled else None,
			}
			for line in lines
		],
		"allocation_unavailable": not reconciled,
		"paid_display": display(gross),
		"refunded_display": display(refunded),
		"remaining_display": display(gross - refunded),
		"has_refund": refunded > 0,
	}


def receipt_response_headers(response, request):
	"""Frappe after_request hook, including permission/error responses."""
	if request.path.rstrip("/") != "/purchase_receipt":
		return
	response.headers["Cache-Control"] = "private, no-store, max-age=0"
	response.headers["Pragma"] = "no-cache"
	response.headers["Referrer-Policy"] = "no-referrer"
	response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"

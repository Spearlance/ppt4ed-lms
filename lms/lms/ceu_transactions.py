"""Mirror Stripe money movements into the LMS so admins can report on them.

Why this exists: before this module the LMS only stored a payment row for one-off
course and event checkouts. Membership renewals recorded credit allocations and
nothing else, so recurring revenue did not exist in the database at all and the
"Revenue" report showed CEU hours instead of dollars. Stripe is the source of
truth for money; this module pulls charges from Stripe, classifies each one
against LMS records, and stores them as `CEU Transaction` rows so reports can
sort, filter and join to the member without calling Stripe on every page load.

Classification is deliberately layered, cheapest and most reliable first:
    1. `LMS Payment` matched on the payment intent  -> Course / Event
    2. Stripe invoice -> subscription -> CEU Membership -> Membership
    3. Stripe Checkout Session metadata (`type` = one_off / event_one_off /
       subscription), which `ceu_stripe.py` already sets
    4. Other, kept and counted rather than dropped, so the totals still
       reconcile against the Stripe dashboard. Donations land here until the
       donations page ships with its own metadata type.
"""

import json

import frappe
from frappe.utils import add_days, cint, flt, get_datetime, now_datetime

SYNC_OVERLAP_DAYS = 3
DEFAULT_PAGE_SIZE = 100
MAX_PAGES = 200

TYPE_COURSE = "Course"
TYPE_EVENT = "Event"
TYPE_MEMBERSHIP = "Membership"
TYPE_OTHER = "Other"


def _require_admin():
    frappe.only_for(["System Manager", "Global Admin"])


# ---------------------------------------------------------------------------
# classification
# ---------------------------------------------------------------------------


def _charge_email(charge: dict) -> str | None:
    billing = charge.get("billing_details") or {}
    return (
        charge.get("receipt_email")
        or billing.get("email")
        or (charge.get("metadata") or {}).get("user")
        or None
    )


def _member_for_email(email: str | None) -> str | None:
    """Only link to a real User row, so the Link field never dangles."""
    if not email:
        return None
    if frappe.db.exists("User", email):
        return email
    match = frappe.db.get_value("User", {"email": email}, "name")
    return match or None


def _item_title(item_type: str | None, item: str | None) -> str | None:
    if not item_type or not item:
        return None
    field = {
        "LMS Course": "title",
        "LMS Event": "title",
        "CEU Membership Plan": "title",
    }.get(item_type)
    if not field:
        return None
    return frappe.db.get_value(item_type, item, field)


def _classify_from_lms_payment(charge: dict) -> dict | None:
    intent = charge.get("payment_intent")
    session_id = (charge.get("metadata") or {}).get("checkout_session_id")
    payment = None
    if intent:
        payment = frappe.db.get_value(
            "LMS Payment",
            {"stripe_payment_intent_id": intent},
            ["name", "member", "payment_for_document_type", "payment_for_document"],
            as_dict=True,
        )
    if not payment and session_id:
        payment = frappe.db.get_value(
            "LMS Payment",
            {"stripe_session_id": session_id},
            ["name", "member", "payment_for_document_type", "payment_for_document"],
            as_dict=True,
        )
    if not payment or not payment.payment_for_document_type:
        return None

    txn_type = TYPE_COURSE if payment.payment_for_document_type == "LMS Course" else TYPE_EVENT
    return {
        "transaction_type": txn_type,
        "item_type": payment.payment_for_document_type,
        "item": payment.payment_for_document,
        "member": _member_for_email(payment.member),
        "classified_by": "lms_payment",
    }


def _classify_from_invoice(charge: dict, invoice_cache: dict | None = None) -> dict | None:
    invoice_id = charge.get("invoice")
    if not invoice_id:
        return None

    invoice = (invoice_cache or {}).get(invoice_id)
    if invoice is None:
        invoice = _retrieve_invoice(invoice_id)
        if invoice_cache is not None:
            invoice_cache[invoice_id] = invoice
    if not invoice:
        return None

    subscription_id = invoice.get("subscription")
    result = {
        "transaction_type": TYPE_MEMBERSHIP,
        "stripe_invoice_id": invoice_id,
        "stripe_subscription_id": subscription_id,
        "classified_by": "invoice_subscription",
    }

    if subscription_id:
        membership = frappe.db.get_value(
            "CEU Membership",
            {"stripe_subscription_id": subscription_id},
            ["name", "member", "plan"],
            as_dict=True,
        )
        if membership:
            result["item_type"] = "CEU Membership Plan"
            result["item"] = membership.plan
            result["member"] = _member_for_email(membership.member)
    return result


def _classify_from_checkout_metadata(charge: dict) -> dict | None:
    """Last resort: ask Stripe which Checkout Session produced this charge."""
    intent = charge.get("payment_intent")
    if not intent:
        return None

    session = _retrieve_session_for_intent(intent)
    if not session:
        return None

    metadata = session.get("metadata") or {}
    checkout_type = metadata.get("type")
    user = metadata.get("user")

    if checkout_type == "one_off" and metadata.get("course"):
        return {
            "transaction_type": TYPE_COURSE,
            "item_type": "LMS Course",
            "item": metadata.get("course"),
            "member": _member_for_email(user),
            "classified_by": "checkout_metadata",
        }
    if checkout_type == "event_one_off" and metadata.get("event"):
        return {
            "transaction_type": TYPE_EVENT,
            "item_type": "LMS Event",
            "item": metadata.get("event"),
            "member": _member_for_email(user),
            "classified_by": "checkout_metadata",
        }
    if checkout_type == "subscription":
        return {
            "transaction_type": TYPE_MEMBERSHIP,
            "item_type": "CEU Membership Plan" if metadata.get("plan") else None,
            "item": metadata.get("plan"),
            "member": _member_for_email(user),
            "classified_by": "checkout_metadata",
        }
    return None


def classify_charge(charge: dict, invoice_cache: dict | None = None) -> dict:
    """Return the type/item/member fields for one Stripe charge."""
    for classifier in (
        lambda: _classify_from_lms_payment(charge),
        lambda: _classify_from_invoice(charge, invoice_cache),
        lambda: _classify_from_checkout_metadata(charge),
    ):
        try:
            result = classifier()
        except Exception:
            frappe.log_error(
                title="CEU Transaction classification failed",
                message=frappe.get_traceback(),
            )
            result = None
        if result:
            return result

    return {
        "transaction_type": TYPE_OTHER,
        "member": _member_for_email(_charge_email(charge)),
        "classified_by": "unclassified",
    }


# ---------------------------------------------------------------------------
# stripe plumbing (thin wrappers so tests can patch one place)
# ---------------------------------------------------------------------------


def _stripe():
    from lms.lms.ceu_stripe import get_stripe

    return get_stripe()


def _retrieve_invoice(invoice_id: str) -> dict | None:
    try:
        return _stripe().Invoice.retrieve(invoice_id)
    except Exception:
        frappe.log_error(
            title="CEU Transaction invoice fetch failed",
            message=f"{invoice_id}\n\n{frappe.get_traceback()}",
        )
        return None


def _retrieve_session_for_intent(intent_id: str) -> dict | None:
    try:
        sessions = _stripe().checkout.Session.list(payment_intent=intent_id, limit=1)
    except Exception:
        frappe.log_error(
            title="CEU Transaction session fetch failed",
            message=f"{intent_id}\n\n{frappe.get_traceback()}",
        )
        return None
    data = sessions.get("data") if isinstance(sessions, dict) else getattr(sessions, "data", None)
    return data[0] if data else None


def _list_charges(created_gte: int | None, limit: int = DEFAULT_PAGE_SIZE):
    """Yield charges newest-first, following Stripe pagination by hand.

    `auto_paging_iter` is avoided on purpose: a slow sync holding an open cursor
    for thousands of charges is exactly how a scheduled job wedges.
    """
    params = {"limit": limit}
    if created_gte:
        params["created"] = {"gte": created_gte}

    starting_after = None
    for _page in range(MAX_PAGES):
        page_params = dict(params)
        if starting_after:
            page_params["starting_after"] = starting_after
        page = _stripe().Charge.list(**page_params)
        data = page.get("data") if isinstance(page, dict) else getattr(page, "data", [])
        if not data:
            return
        for charge in data:
            yield charge
        has_more = page.get("has_more") if isinstance(page, dict) else getattr(page, "has_more", False)
        if not has_more:
            return
        starting_after = data[-1].get("id")


# ---------------------------------------------------------------------------
# writing
# ---------------------------------------------------------------------------


def charge_to_row(charge: dict, invoice_cache: dict | None = None) -> dict:
    """Flatten a Stripe charge into CEU Transaction fields."""
    gross = flt(charge.get("amount") or 0) / 100
    refunded = flt(charge.get("amount_refunded") or 0) / 100
    status = "Succeeded" if charge.get("paid") and charge.get("status") == "succeeded" else "Failed"

    classified = classify_charge(charge, invoice_cache=invoice_cache)
    item_type = classified.get("item_type")
    item = classified.get("item")

    row = {
        "stripe_id": charge.get("id"),
        "transaction_date": _charge_datetime(charge),
        "transaction_type": classified.get("transaction_type") or TYPE_OTHER,
        "status": status,
        "description": charge.get("description") or _item_title(item_type, item) or "",
        "gross_amount": gross,
        "refunded_amount": refunded,
        "net_amount": gross - refunded,
        "currency": (charge.get("currency") or "usd").upper(),
        "customer_email": _charge_email(charge),
        "member": classified.get("member"),
        "item_type": item_type,
        "item": item,
        "item_title": _item_title(item_type, item),
        "stripe_customer_id": charge.get("customer"),
        "stripe_payment_intent_id": charge.get("payment_intent"),
        "stripe_invoice_id": classified.get("stripe_invoice_id") or charge.get("invoice"),
        "stripe_subscription_id": classified.get("stripe_subscription_id"),
        "stripe_metadata": json.dumps(charge.get("metadata") or {}),
        "classified_by": classified.get("classified_by"),
        "synced_at": now_datetime(),
    }
    return row


def _charge_datetime(charge: dict):
    created = charge.get("created")
    if not created:
        return now_datetime()
    from datetime import datetime, timezone

    from frappe.utils import convert_utc_to_system_timezone

    utc_dt = datetime.fromtimestamp(cint(created), tz=timezone.utc)
    try:
        return convert_utc_to_system_timezone(utc_dt.replace(tzinfo=None))
    except Exception:
        return utc_dt.replace(tzinfo=None)


def upsert_transaction(row: dict) -> str | None:
    """Insert or refresh one transaction. Idempotent on the Stripe charge id."""
    stripe_id = row.get("stripe_id")
    if not stripe_id:
        return None

    existing = frappe.db.exists("CEU Transaction", stripe_id)
    if existing:
        doc = frappe.get_doc("CEU Transaction", stripe_id)
        # Refunds and late classification are the only things that change.
        for field in (
            "refunded_amount",
            "status",
            "transaction_type",
            "item_type",
            "item",
            "item_title",
            "member",
            "stripe_invoice_id",
            "stripe_subscription_id",
            "classified_by",
            "synced_at",
        ):
            if row.get(field) is not None:
                doc.set(field, row.get(field))
        doc.flags.ignore_permissions = True
        doc.save()
        return doc.name

    doc = frappe.get_doc({"doctype": "CEU Transaction", **row})
    doc.flags.ignore_permissions = True
    doc.insert()
    return doc.name


def sync_transactions(since_days: int | None = None) -> dict:
    """Pull charges from Stripe and upsert them. Returns a small summary."""
    created_gte = None
    if since_days:
        created_gte = int(get_datetime(add_days(now_datetime(), -abs(cint(since_days)))).timestamp())

    invoice_cache: dict = {}
    created = updated = failed = 0

    for charge in _list_charges(created_gte):
        charge_id = charge.get("id")
        try:
            existed = bool(charge_id and frappe.db.exists("CEU Transaction", charge_id))
            upsert_transaction(charge_to_row(charge, invoice_cache=invoice_cache))
            if existed:
                updated += 1
            else:
                created += 1
        except Exception:
            failed += 1
            frappe.log_error(
                title="CEU Transaction sync failed for charge",
                message=f"{charge_id}\n\n{frappe.get_traceback()}",
            )

    frappe.db.commit()
    return {"created": created, "updated": updated, "failed": failed}


def sync_recent() -> dict:
    """Hourly scheduler entry. Overlapping window so refunds get picked up."""
    return sync_transactions(since_days=SYNC_OVERLAP_DAYS)


def record_invoice_transaction(invoice_id: str, subscription_id: str | None = None) -> str | None:
    """Record membership revenue the moment `invoice.paid` arrives.

    Without this, subscription money only appears at the next hourly sync, and
    before this module it was never recorded at all. Fails open — a reporting
    row is never worth breaking a payment webhook over.
    """
    if not invoice_id:
        return None
    try:
        invoice = _retrieve_invoice(invoice_id)
        if not invoice:
            return None

        charge_id = invoice.get("charge") or invoice.get("id")
        amount = flt(invoice.get("amount_paid") or invoice.get("total") or 0) / 100
        subscription_id = subscription_id or invoice.get("subscription")

        membership = None
        if subscription_id:
            membership = frappe.db.get_value(
                "CEU Membership",
                {"stripe_subscription_id": subscription_id},
                ["member", "plan"],
                as_dict=True,
            )

        row = {
            "stripe_id": charge_id,
            "transaction_date": _charge_datetime(invoice),
            "transaction_type": TYPE_MEMBERSHIP,
            "status": "Succeeded",
            "description": invoice.get("description") or "Membership renewal",
            "gross_amount": amount,
            "refunded_amount": 0,
            "net_amount": amount,
            "currency": (invoice.get("currency") or "usd").upper(),
            "customer_email": invoice.get("customer_email"),
            "member": _member_for_email(
                (membership or {}).get("member") or invoice.get("customer_email")
            ),
            "item_type": "CEU Membership Plan" if membership else None,
            "item": (membership or {}).get("plan"),
            "item_title": _item_title("CEU Membership Plan", (membership or {}).get("plan")),
            "stripe_customer_id": invoice.get("customer"),
            "stripe_invoice_id": invoice.get("id"),
            "stripe_subscription_id": subscription_id,
            "stripe_metadata": json.dumps(invoice.get("metadata") or {}),
            "classified_by": "webhook",
            "synced_at": now_datetime(),
        }
        return upsert_transaction(row)
    except Exception:
        frappe.log_error(
            title="CEU Transaction invoice recording failed",
            message=f"{invoice_id}\n\n{frappe.get_traceback()}",
        )
        return None


# ---------------------------------------------------------------------------
# admin endpoints
# ---------------------------------------------------------------------------


@frappe.whitelist()
def sync_now(since_days: int | None = 30) -> dict:
    """Queue a Stripe sync. Backgrounded so a long backfill can't time out."""
    _require_admin()
    frappe.enqueue(
        "lms.lms.ceu_transactions.sync_transactions",
        queue="long",
        timeout=1800,
        since_days=cint(since_days) or None,
    )
    return {"queued": True, "since_days": cint(since_days) or None}


@frappe.whitelist()
def get_sync_status() -> dict:
    _require_admin()
    last = frappe.db.sql(
        "SELECT MAX(synced_at) AS last_synced, COUNT(*) AS rows_stored FROM `tabCEU Transaction`",
        as_dict=True,
    )
    unclassified = frappe.db.count("CEU Transaction", {"transaction_type": TYPE_OTHER})
    return {
        "last_synced": last[0].last_synced if last else None,
        "rows_stored": last[0].rows_stored if last else 0,
        "unclassified": unclassified,
    }

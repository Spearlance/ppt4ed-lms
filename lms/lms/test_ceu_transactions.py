import frappe
from frappe.tests import UnitTestCase
from frappe.utils import add_days, now_datetime, nowdate
from unittest.mock import patch


def _charge(**overrides):
    charge = {
        "id": "ch_test_default",
        "amount": 12900,
        "amount_refunded": 0,
        "currency": "usd",
        "created": 1758153600,  # 2025-09-18 UTC
        "paid": True,
        "status": "succeeded",
        "description": "Test charge",
        "customer": "cus_test",
        "payment_intent": "pi_test_default",
        "billing_details": {"email": "buyer@example.com"},
        "metadata": {},
    }
    charge.update(overrides)
    return charge


class TestCEUTransactions(UnitTestCase):
    def tearDown(self):
        for row in frappe.get_all(
            "CEU Transaction", filters=[["stripe_id", "like", "ch_test_%"]], pluck="name"
        ):
            frappe.delete_doc("CEU Transaction", row, force=True, ignore_permissions=True)

        # Test plans are dev clutter once their memberships are gone.
        for plan in ("Txn Test Plan", "Txn Webhook Plan"):
            if frappe.db.exists("CEU Membership Plan", plan) and not frappe.db.exists(
                "CEU Membership", {"plan": plan}
            ):
                frappe.delete_doc(
                    "CEU Membership Plan", plan, force=True, ignore_permissions=True
                )
        frappe.db.commit()

    # -- classification ---------------------------------------------------

    def test_classifies_course_purchase_from_lms_payment(self):
        from lms.lms.ceu_transactions import classify_charge

        courses = frappe.get_all("LMS Course", limit=1, pluck="name")
        if not courses:
            self.skipTest("No LMS Course exists for testing")

        payment = frappe.get_doc({
            "doctype": "LMS Payment",
            "member": "Administrator",
            "amount": 129,
            "currency": "USD",
            "payment_for_document_type": "LMS Course",
            "payment_for_document": courses[0],
            "payment_received": 1,
            "stripe_payment_intent_id": "pi_test_course",
        }).insert(ignore_permissions=True)

        try:
            result = classify_charge(_charge(payment_intent="pi_test_course"))
            self.assertEqual(result["transaction_type"], "Course")
            self.assertEqual(result["item_type"], "LMS Course")
            self.assertEqual(result["item"], courses[0])
            self.assertEqual(result["classified_by"], "lms_payment")
        finally:
            frappe.delete_doc("LMS Payment", payment.name, force=True, ignore_permissions=True)

    def test_classifies_membership_from_invoice_subscription(self):
        from lms.lms.ceu_transactions import classify_charge

        if not frappe.db.exists("CEU Membership Plan", "Txn Test Plan"):
            frappe.get_doc({
                "doctype": "CEU Membership Plan",
                "title": "Txn Test Plan",
                "plan_type": "Professional",
                "ceu_hours": 15.0,
                "price": 149.00,
                "active": 1,
            }).insert(ignore_permissions=True)

        membership = frappe.get_doc({
            "doctype": "CEU Membership",
            "member": "Administrator",
            "plan": "Txn Test Plan",
            "membership_type": "Individual",
            "stripe_subscription_id": "sub_test_txn",
            "status": "Active",
            "start_date": nowdate(),
            "end_date": add_days(nowdate(), 365),
            "credit_balance": 15,
        }).insert(ignore_permissions=True)

        try:
            with patch(
                "lms.lms.ceu_transactions._retrieve_invoice",
                return_value={"id": "in_test_txn", "subscription": "sub_test_txn"},
            ):
                result = classify_charge(_charge(invoice="in_test_txn"))

            self.assertEqual(result["transaction_type"], "Membership")
            self.assertEqual(result["item_type"], "CEU Membership Plan")
            self.assertEqual(result["item"], "Txn Test Plan")
            self.assertEqual(result["classified_by"], "invoice_subscription")
        finally:
            frappe.delete_doc("CEU Membership", membership.name, force=True, ignore_permissions=True)

    def test_classifies_event_from_checkout_metadata(self):
        from lms.lms.ceu_transactions import classify_charge

        session = {
            "metadata": {
                "type": "event_one_off",
                "event": "test-event",
                "user": "buyer@example.com",
            }
        }
        with patch("lms.lms.ceu_transactions._retrieve_session_for_intent", return_value=session):
            result = classify_charge(_charge(payment_intent="pi_test_event_meta"))

        self.assertEqual(result["transaction_type"], "Event")
        self.assertEqual(result["item_type"], "LMS Event")
        self.assertEqual(result["item"], "test-event")
        self.assertEqual(result["classified_by"], "checkout_metadata")

    def test_unmatched_charge_is_kept_as_other(self):
        """Donations and anything else must be counted, never dropped."""
        from lms.lms.ceu_transactions import classify_charge

        with patch("lms.lms.ceu_transactions._retrieve_session_for_intent", return_value=None):
            result = classify_charge(_charge(payment_intent="pi_test_unknown"))

        self.assertEqual(result["transaction_type"], "Other")
        self.assertEqual(result["classified_by"], "unclassified")

    # -- row building and upsert ------------------------------------------

    def test_charge_to_row_converts_cents_and_nets_refunds(self):
        from lms.lms.ceu_transactions import charge_to_row

        with patch("lms.lms.ceu_transactions._retrieve_session_for_intent", return_value=None):
            row = charge_to_row(
                _charge(id="ch_test_refund", amount=20000, amount_refunded=5000)
            )

        self.assertEqual(row["gross_amount"], 200.0)
        self.assertEqual(row["refunded_amount"], 50.0)
        self.assertEqual(row["net_amount"], 150.0)
        self.assertEqual(row["currency"], "USD")

    def test_upsert_is_idempotent_and_picks_up_refunds(self):
        from lms.lms.ceu_transactions import charge_to_row, upsert_transaction

        with patch("lms.lms.ceu_transactions._retrieve_session_for_intent", return_value=None):
            first = charge_to_row(_charge(id="ch_test_idem", amount=10000))
            upsert_transaction(first)
            upsert_transaction(first)
            refunded = charge_to_row(
                _charge(id="ch_test_idem", amount=10000, amount_refunded=10000)
            )
            upsert_transaction(refunded)

        rows = frappe.get_all("CEU Transaction", filters={"stripe_id": "ch_test_idem"})
        self.assertEqual(len(rows), 1)

        doc = frappe.get_doc("CEU Transaction", "ch_test_idem")
        self.assertEqual(doc.refunded_amount, 100.0)
        self.assertEqual(doc.net_amount, 0.0)
        self.assertEqual(doc.status, "Refunded")

    def test_partial_refund_sets_partially_refunded_status(self):
        from lms.lms.ceu_transactions import charge_to_row, upsert_transaction

        with patch("lms.lms.ceu_transactions._retrieve_session_for_intent", return_value=None):
            upsert_transaction(
                charge_to_row(_charge(id="ch_test_partial", amount=10000, amount_refunded=2500))
            )

        doc = frappe.get_doc("CEU Transaction", "ch_test_partial")
        self.assertEqual(doc.status, "Partially Refunded")
        self.assertEqual(doc.net_amount, 75.0)

    def test_transactions_cannot_be_hand_edited_into_negative_amounts(self):
        from lms.lms.ceu_transactions import charge_to_row, upsert_transaction

        with patch("lms.lms.ceu_transactions._retrieve_session_for_intent", return_value=None):
            upsert_transaction(charge_to_row(_charge(id="ch_test_negative", amount=5000)))

        doc = frappe.get_doc("CEU Transaction", "ch_test_negative")
        doc.gross_amount = -1
        with self.assertRaises(frappe.ValidationError):
            doc.save(ignore_permissions=True)

    # -- reporting --------------------------------------------------------

    def test_money_summary_totals_and_type_split(self):
        from lms.lms.ceu_reports import get_money_summary

        today = now_datetime()
        rows = [
            {
                "doctype": "CEU Transaction",
                "stripe_id": "ch_test_sum_course",
                "transaction_date": today,
                "transaction_type": "Course",
                "status": "Succeeded",
                "gross_amount": 100,
                "refunded_amount": 0,
                "currency": "USD",
            },
            {
                "doctype": "CEU Transaction",
                "stripe_id": "ch_test_sum_membership",
                "transaction_date": today,
                "transaction_type": "Membership",
                "status": "Succeeded",
                "gross_amount": 300,
                "refunded_amount": 50,
                "currency": "USD",
            },
            {
                "doctype": "CEU Transaction",
                "stripe_id": "ch_test_sum_failed",
                "transaction_date": today,
                "transaction_type": "Course",
                "status": "Failed",
                "gross_amount": 999,
                "refunded_amount": 0,
                "currency": "USD",
            },
        ]
        for row in rows:
            doc = frappe.get_doc(row)
            doc.flags.ignore_permissions = True
            doc.insert()
        frappe.db.commit()

        summary = get_money_summary(from_date=nowdate(), to_date=nowdate())

        # Failed charges never count as money in.
        self.assertEqual(summary["totals"]["transactions"], 2)
        self.assertEqual(summary["totals"]["gross"], 400)
        self.assertEqual(summary["totals"]["refunded"], 50)
        self.assertEqual(summary["totals"]["net"], 350)

        by_type = {r["transaction_type"]: r for r in summary["by_type"]}
        self.assertEqual(by_type["Membership"]["net"], 250)
        self.assertEqual(by_type["Course"]["net"], 100)

    def test_invoice_paid_records_membership_dollars(self):
        from lms.lms.ceu_transactions import record_invoice_transaction

        if not frappe.db.exists("CEU Membership Plan", "Txn Webhook Plan"):
            frappe.get_doc({
                "doctype": "CEU Membership Plan",
                "title": "Txn Webhook Plan",
                "plan_type": "Professional",
                "ceu_hours": 15.0,
                "price": 149.00,
                "active": 1,
            }).insert(ignore_permissions=True)

        membership = frappe.get_doc({
            "doctype": "CEU Membership",
            "member": "Administrator",
            "plan": "Txn Webhook Plan",
            "membership_type": "Individual",
            "stripe_subscription_id": "sub_test_webhook_txn",
            "status": "Active",
            "start_date": nowdate(),
            "end_date": add_days(nowdate(), 365),
            "credit_balance": 15,
        }).insert(ignore_permissions=True)

        invoice = {
            "id": "in_test_webhook",
            "charge": "ch_test_webhook",
            "amount_paid": 14900,
            "currency": "usd",
            "customer": "cus_test",
            "customer_email": "Administrator",
            "subscription": "sub_test_webhook_txn",
            "created": 1758153600,
            "metadata": {},
        }

        try:
            with patch("lms.lms.ceu_transactions._retrieve_invoice", return_value=invoice):
                name = record_invoice_transaction("in_test_webhook", subscription_id="sub_test_webhook_txn")

            self.assertEqual(name, "ch_test_webhook")
            doc = frappe.get_doc("CEU Transaction", "ch_test_webhook")
            self.assertEqual(doc.transaction_type, "Membership")
            self.assertEqual(doc.gross_amount, 149.0)
            self.assertEqual(doc.item, "Txn Webhook Plan")
            self.assertEqual(doc.classified_by, "webhook")
        finally:
            frappe.delete_doc("CEU Membership", membership.name, force=True, ignore_permissions=True)

    def test_invoice_recording_never_raises(self):
        """A reporting row must never break a payment webhook."""
        from lms.lms.ceu_transactions import record_invoice_transaction

        with patch(
            "lms.lms.ceu_transactions._retrieve_invoice",
            side_effect=Exception("stripe down"),
        ):
            self.assertIsNone(record_invoice_transaction("in_test_boom"))

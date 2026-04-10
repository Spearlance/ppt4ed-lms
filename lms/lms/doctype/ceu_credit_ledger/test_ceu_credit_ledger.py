import frappe
from frappe.tests import UnitTestCase
from frappe.utils import now_datetime


class TestCEUCreditLedger(UnitTestCase):
    def test_create_allocation_entry(self):
        doc = frappe.get_doc({
            "doctype": "CEU Credit Ledger",
            "user": "Administrator",
            "transaction_type": "Allocation",
            "hours": 20.0,
            "balance_after": 20.0,
            "timestamp": now_datetime()
        })
        doc.insert(ignore_permissions=True)
        self.assertEqual(doc.transaction_type, "Allocation")
        self.assertEqual(doc.hours, 20.0)

    def test_create_enrollment_debit(self):
        doc = frappe.get_doc({
            "doctype": "CEU Credit Ledger",
            "user": "Administrator",
            "transaction_type": "Enrollment",
            "hours": -2.0,
            "balance_after": 18.0,
            "timestamp": now_datetime()
        })
        doc.insert(ignore_permissions=True)
        self.assertEqual(doc.hours, -2.0)
        self.assertEqual(doc.balance_after, 18.0)

    def test_cannot_modify_existing_entry(self):
        doc = frappe.get_doc({
            "doctype": "CEU Credit Ledger",
            "user": "Administrator",
            "transaction_type": "Allocation",
            "hours": 20.0,
            "balance_after": 20.0,
            "timestamp": now_datetime()
        })
        doc.insert(ignore_permissions=True)

        doc.hours = 999.0
        with self.assertRaises(frappe.ValidationError):
            doc.save(ignore_permissions=True)

    def test_cannot_delete_entry(self):
        doc = frappe.get_doc({
            "doctype": "CEU Credit Ledger",
            "user": "Administrator",
            "transaction_type": "Allocation",
            "hours": 10.0,
            "balance_after": 10.0,
            "timestamp": now_datetime()
        })
        doc.insert(ignore_permissions=True)

        # Temporarily clear in_test flag to verify production behavior
        frappe.flags.in_test = False
        try:
            with self.assertRaises(frappe.ValidationError):
                doc.delete(ignore_permissions=True)
        finally:
            frappe.flags.in_test = True

    def test_ledger_accepts_stripe_payment_id(self):
        doc = frappe.get_doc({
            "doctype": "CEU Credit Ledger",
            "user": "Administrator",
            "transaction_type": "Allocation",
            "hours": 20.0,
            "balance_after": 20.0,
            "timestamp": now_datetime(),
            "stripe_payment_id": "ch_test_123"
        })
        doc.insert(ignore_permissions=True)
        self.assertEqual(doc.stripe_payment_id, "ch_test_123")

    def test_ledger_accepts_notes(self):
        doc = frappe.get_doc({
            "doctype": "CEU Credit Ledger",
            "user": "Administrator",
            "transaction_type": "Admin Adjustment",
            "hours": 5.0,
            "balance_after": 25.0,
            "timestamp": now_datetime(),
            "notes": "Manual credit restore per support ticket #42"
        })
        doc.insert(ignore_permissions=True)
        self.assertEqual(doc.notes, "Manual credit restore per support ticket #42")

    def test_ledger_accepts_direct_purchase(self):
        doc = frappe.get_doc({
            "doctype": "CEU Credit Ledger",
            "user": "Administrator",
            "transaction_type": "Direct Purchase",
            "hours": 0,
            "balance_after": 0,
            "timestamp": now_datetime(),
            "stripe_payment_id": "cs_test_456"
        })
        doc.insert(ignore_permissions=True)
        self.assertEqual(doc.transaction_type, "Direct Purchase")

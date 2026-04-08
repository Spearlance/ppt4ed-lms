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

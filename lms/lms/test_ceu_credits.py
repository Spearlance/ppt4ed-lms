import frappe
from frappe.tests import UnitTestCase
from frappe.utils import today, add_years


class TestCEUCredits(UnitTestCase):
    def setUp(self):
        if not frappe.db.exists("CEU Membership Plan", "Credit Test Plan"):
            frappe.get_doc({
                "doctype": "CEU Membership Plan",
                "title": "Credit Test Plan",
                "plan_type": "Professional",
                "ceu_hours": 20.0,
                "price": 199.00,
                "active": 1
            }).insert(ignore_permissions=True)

        self.membership = frappe.get_doc({
            "doctype": "CEU Membership",
            "member": "Administrator",
            "plan": "Credit Test Plan",
            "membership_type": "Professional",
            "status": "Active",
            "start_date": today(),
            "end_date": add_years(today(), 1),
            "credit_balance": 0
        }).insert(ignore_permissions=True)

    def test_allocate_credits(self):
        from lms.lms.ceu_credits import allocate_credits

        allocate_credits(self.membership.name, 20.0)

        self.membership.reload()
        self.assertEqual(self.membership.credit_balance, 20.0)

        ledger = frappe.get_last_doc("CEU Credit Ledger", filters={
            "membership": self.membership.name,
            "transaction_type": "Allocation"
        })
        self.assertEqual(ledger.hours, 20.0)
        self.assertEqual(ledger.balance_after, 20.0)

    def test_debit_credits(self):
        from lms.lms.ceu_credits import allocate_credits, debit_credits

        allocate_credits(self.membership.name, 20.0)
        debit_credits(self.membership.name, "Administrator", 2.0, course=None)

        self.membership.reload()
        self.assertEqual(self.membership.credit_balance, 18.0)

    def test_debit_insufficient_credits_raises(self):
        from lms.lms.ceu_credits import allocate_credits, debit_credits

        allocate_credits(self.membership.name, 5.0)

        with self.assertRaises(frappe.ValidationError):
            debit_credits(self.membership.name, "Administrator", 10.0, course=None)

    def test_debit_inactive_membership_raises(self):
        from lms.lms.ceu_credits import allocate_credits, debit_credits

        allocate_credits(self.membership.name, 20.0)
        self.membership.status = "Cancelled"
        self.membership.save(ignore_permissions=True)

        with self.assertRaises(frappe.ValidationError):
            debit_credits(self.membership.name, "Administrator", 2.0, course=None)

    def test_debit_uses_locked_balance(self):
        """Verify debit reads the actual DB balance, not a stale cached value."""
        from lms.lms.ceu_credits import allocate_credits, debit_credits

        allocate_credits(self.membership.name, 10.0)

        # Simulate stale read: manually change balance in DB without going through ORM
        frappe.db.set_value("CEU Membership", self.membership.name, "credit_balance", 3.0)

        # Should use the DB value (3.0), not the ORM-cached value (10.0)
        with self.assertRaises(frappe.ValidationError):
            debit_credits(self.membership.name, "Administrator", 5.0, course=None)

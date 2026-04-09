import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_years, today


class TestCEUAdmin(IntegrationTestCase):
    """Integration tests for ceu_admin — admin management APIs."""

    def setUp(self):
        self._cleanup()

    def tearDown(self):
        self._cleanup()

    def _cleanup(self):
        frappe.db.delete(
            "Company Member",
            {"user": "Administrator", "parenttype": "Company Account"},
        )
        for name in frappe.get_all(
            "Company Account",
            filters={"company_name": ["like", "Test_Admin_%"]},
            pluck="name",
        ):
            frappe.delete_doc("Company Account", name, force=True)
        for name in frappe.get_all(
            "CEU Membership", filters={"member": "Administrator"}, pluck="name"
        ):
            for entry in frappe.get_all(
                "CEU Credit Ledger", filters={"membership": name}, pluck="name"
            ):
                frappe.delete_doc("CEU Credit Ledger", entry, force=True)
            frappe.delete_doc("CEU Membership", name, force=True)
        frappe.db.commit()

    # ─────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────

    def _get_or_create_plan(self, plan_type="Professional"):
        name = f"Test Admin {plan_type} Plan"
        if not frappe.db.exists("CEU Membership Plan", name):
            frappe.get_doc(
                {
                    "doctype": "CEU Membership Plan",
                    "title": name,
                    "plan_type": plan_type,
                    "ceu_hours": 50,
                    "price": 199,
                }
            ).insert(ignore_permissions=True)
        return name

    def _make_professional_membership(self, balance=20.0):
        plan = self._get_or_create_plan("Professional")
        return frappe.get_doc(
            {
                "doctype": "CEU Membership",
                "member": "Administrator",
                "plan": plan,
                "membership_type": "Professional",
                "status": "Active",
                "start_date": today(),
                "end_date": add_years(today(), 1),
                "credit_balance": balance,
            }
        ).insert(ignore_permissions=True)

    def _make_company(self, name_suffix, with_member=True, with_admin=False):
        members = []
        admins = []
        if with_member:
            members = [{"user": "Administrator", "status": "Active"}]
        if with_admin:
            admins = [{"user": "Administrator"}]
        return frappe.get_doc(
            {
                "doctype": "Company Account",
                "company_name": f"Test_Admin_{name_suffix}",
                "members": members,
                "admins": admins,
            }
        ).insert(ignore_permissions=True)

    # ─────────────────────────────────────────────
    # get_member_admin_details
    # ─────────────────────────────────────────────

    def test_get_member_admin_details_one_off(self):
        """Returns one_off user_type when user has no memberships."""
        from lms.lms.ceu_admin import get_member_admin_details

        result = get_member_admin_details("Administrator")
        self.assertEqual(result["user"], "Administrator")
        self.assertEqual(result["user_type"], "one_off")
        self.assertIsNone(result["membership"])
        self.assertIsNone(result["company"])
        self.assertIsInstance(result["enrollments"], list)

    def test_get_member_admin_details_professional(self):
        """Returns professional user_type and membership data."""
        from lms.lms.ceu_admin import get_member_admin_details

        membership = self._make_professional_membership(balance=30.0)
        result = get_member_admin_details("Administrator")

        self.assertEqual(result["user_type"], "professional")
        self.assertIsNotNone(result["membership"])
        self.assertEqual(result["membership"]["name"], membership.name)
        self.assertEqual(result["membership"]["credit_balance"], 30.0)

    def test_get_member_admin_details_company(self):
        """Returns company user_type and company data."""
        from lms.lms.ceu_admin import get_member_admin_details

        company = self._make_company("MemberDetail")
        result = get_member_admin_details("Administrator")

        self.assertEqual(result["user_type"], "company")
        self.assertIsNotNone(result["company"])
        self.assertEqual(result["company"]["name"], company.name)
        self.assertEqual(result["company"]["member_status"], "Active")

    def test_get_member_admin_details_company_admin_role(self):
        """Correctly identifies company admin vs member role."""
        from lms.lms.ceu_admin import get_member_admin_details

        self._make_company("AdminRole", with_member=True, with_admin=True)
        result = get_member_admin_details("Administrator")

        self.assertEqual(result["company"]["role"], "Admin")

    def test_get_member_admin_details_enrollments_list(self):
        """Enrollments key is always a list (empty when none)."""
        from lms.lms.ceu_admin import get_member_admin_details

        result = get_member_admin_details("Administrator")
        self.assertIsInstance(result["enrollments"], list)

    # ─────────────────────────────────────────────
    # admin_adjust_credits
    # ─────────────────────────────────────────────

    def test_admin_adjust_credits_adds(self):
        """Positive hours increase the credit balance."""
        from lms.lms.ceu_admin import admin_adjust_credits

        membership = self._make_professional_membership(balance=10.0)
        result = admin_adjust_credits(membership.name, 5.0, "Bonus")

        self.assertEqual(result["credit_balance"], 15.0)
        fresh = frappe.get_doc("CEU Membership", membership.name)
        self.assertEqual(fresh.credit_balance, 15.0)

    def test_admin_adjust_credits_deducts(self):
        """Negative hours reduce the credit balance."""
        from lms.lms.ceu_admin import admin_adjust_credits

        membership = self._make_professional_membership(balance=10.0)
        result = admin_adjust_credits(membership.name, -3.0, "Correction")

        self.assertEqual(result["credit_balance"], 7.0)

    def test_admin_adjust_credits_blocks_below_zero(self):
        """Cannot reduce credits below zero."""
        from lms.lms.ceu_admin import admin_adjust_credits

        membership = self._make_professional_membership(balance=2.0)
        with self.assertRaises(frappe.exceptions.ValidationError):
            admin_adjust_credits(membership.name, -5.0, "Too much")

    def test_admin_adjust_credits_creates_ledger_entry(self):
        """Each adjustment creates a CEU Credit Ledger entry."""
        from lms.lms.ceu_admin import admin_adjust_credits

        membership = self._make_professional_membership(balance=10.0)
        admin_adjust_credits(membership.name, 4.0, "Test reason")

        entries = frappe.get_all(
            "CEU Credit Ledger",
            filters={"membership": membership.name, "transaction_type": "Admin Adjustment"},
            fields=["hours", "balance_after", "course"],
        )
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["hours"], 4.0)
        self.assertEqual(entries[0]["balance_after"], 14.0)
        self.assertEqual(entries[0]["course"], "Test reason")

    # ─────────────────────────────────────────────
    # get_company_admin_details
    # ─────────────────────────────────────────────

    def test_get_company_admin_details_returns_members(self):
        """Returns list of members with user details."""
        from lms.lms.ceu_admin import get_company_admin_details

        company = self._make_company("Details")
        result = get_company_admin_details(company.name)

        self.assertEqual(result["name"], company.name)
        self.assertIsInstance(result["members"], list)
        self.assertEqual(len(result["members"]), 1)
        self.assertEqual(result["members"][0]["user"], "Administrator")
        self.assertEqual(result["members"][0]["status"], "Active")

    def test_get_company_admin_details_returns_admins(self):
        """Returns list of admins."""
        from lms.lms.ceu_admin import get_company_admin_details

        company = self._make_company("AdminList", with_member=True, with_admin=True)
        result = get_company_admin_details(company.name)

        self.assertIsInstance(result["admins"], list)
        admin_users = [a["user"] for a in result["admins"]]
        self.assertIn("Administrator", admin_users)

    def test_get_company_admin_details_membership_none_when_unlinked(self):
        """Membership is None when company has no linked membership."""
        from lms.lms.ceu_admin import get_company_admin_details

        company = self._make_company("NoMembership", with_member=False)
        result = get_company_admin_details(company.name)

        self.assertIsNone(result["membership"])

    def test_get_company_admin_details_enrollment_count(self):
        """Each member row includes enrollment_count (0 when none)."""
        from lms.lms.ceu_admin import get_company_admin_details

        company = self._make_company("EnrollCount")
        result = get_company_admin_details(company.name)

        member_row = result["members"][0]
        self.assertIn("enrollment_count", member_row)
        self.assertIsInstance(member_row["enrollment_count"], int)

    # ─────────────────────────────────────────────
    # admin_update_company
    # ─────────────────────────────────────────────

    def test_admin_update_company_allowed_fields(self):
        """Updates billing_email and max_seats."""
        from lms.lms.ceu_admin import admin_update_company

        company = self._make_company("UpdateFields", with_member=False)
        result = admin_update_company(
            company.name,
            {"billing_email": "admin@example.com", "max_seats": 25},
        )

        self.assertEqual(result["status"], "updated")
        fresh = frappe.get_doc("Company Account", company.name)
        self.assertEqual(fresh.billing_email, "admin@example.com")
        self.assertEqual(fresh.max_seats, 25)

    def test_admin_update_company_ignores_disallowed_fields(self):
        """Disallowed fields are silently ignored."""
        from lms.lms.ceu_admin import admin_update_company

        company = self._make_company("IgnoreFields", with_member=False)
        original_name = company.company_name
        admin_update_company(company.name, {"company_name": "Hacked Name"})

        fresh = frappe.get_doc("Company Account", company.name)
        self.assertEqual(fresh.company_name, original_name)

    def test_admin_update_company_accepts_json_string(self):
        """fields param works as a JSON string (API call path)."""
        import json

        from lms.lms.ceu_admin import admin_update_company

        company = self._make_company("JsonFields", with_member=False)
        admin_update_company(company.name, json.dumps({"max_seats": 10}))

        fresh = frappe.get_doc("Company Account", company.name)
        self.assertEqual(fresh.max_seats, 10)

    # ─────────────────────────────────────────────
    # admin_remove_member_from_company
    # ─────────────────────────────────────────────

    def test_admin_remove_member_sets_status_removed(self):
        """Sets the member's status to Removed."""
        from lms.lms.ceu_admin import admin_remove_member_from_company

        company = self._make_company("RemoveMember")
        result = admin_remove_member_from_company("Administrator", company.name)

        self.assertEqual(result["status"], "removed")
        fresh = frappe.get_doc("Company Account", company.name)
        statuses = [m.status for m in fresh.members if m.user == "Administrator"]
        self.assertEqual(statuses, ["Removed"])

    # ─────────────────────────────────────────────
    # admin_promote_to_company_admin
    # ─────────────────────────────────────────────

    def test_admin_promote_adds_user_to_admins(self):
        """Adds Administrator to company admins list."""
        from lms.lms.ceu_admin import admin_promote_to_company_admin

        company = self._make_company("Promote")
        result = admin_promote_to_company_admin("Administrator", company.name)

        self.assertEqual(result["status"], "promoted")
        fresh = frappe.get_doc("Company Account", company.name)
        admin_users = [a.user for a in fresh.admins]
        self.assertIn("Administrator", admin_users)

    def test_admin_promote_throws_if_already_admin(self):
        """Throws when user is already in the admins list."""
        from lms.lms.ceu_admin import admin_promote_to_company_admin

        company = self._make_company("AlreadyAdmin", with_member=True, with_admin=True)
        with self.assertRaises(frappe.exceptions.ValidationError):
            admin_promote_to_company_admin("Administrator", company.name)

    # ─────────────────────────────────────────────
    # get_company_credit_history
    # ─────────────────────────────────────────────

    def test_get_company_credit_history_returns_empty_without_membership(self):
        """Returns empty list when company has no linked membership."""
        from lms.lms.ceu_admin import get_company_credit_history

        company = self._make_company("NoCreditHistory", with_member=False)
        result = get_company_credit_history(company.name)
        self.assertEqual(result, [])

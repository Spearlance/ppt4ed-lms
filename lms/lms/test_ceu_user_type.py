import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import today, add_years


class TestGetUserType(IntegrationTestCase):
    """Tests for get_user_type — derives account type from DB relationships."""

    def setUp(self):
        """Clean up any company memberships and CEU memberships for Administrator."""
        self._cleanup()

    def tearDown(self):
        self._cleanup()

    def _cleanup(self):
        # Remove Administrator from all company member lists
        frappe.db.delete("Company Member", {
            "user": "Administrator",
            "parenttype": "Company Account",
        })
        # Delete test companies
        for name in frappe.get_all("Company Account", filters={"company_name": ["like", "Test_UT_%"]}, pluck="name"):
            frappe.delete_doc("Company Account", name, force=True)
        # Delete Administrator's CEU memberships
        for name in frappe.get_all("CEU Membership", filters={"member": "Administrator"}, pluck="name"):
            for entry in frappe.get_all("CEU Credit Ledger", filters={"membership": name}, pluck="name"):
                frappe.delete_doc("CEU Credit Ledger", entry, force=True)
            frappe.delete_doc("CEU Membership", name, force=True)
        frappe.db.commit()

    def test_returns_one_off_when_no_memberships(self):
        """User with no company or professional memberships is one_off."""
        from lms.lms.ceu_user_type import get_user_type
        result = get_user_type("Administrator")
        self.assertEqual(result["type"], "one_off")

    def test_returns_professional_when_active_membership(self):
        """User with active Professional CEU Membership is professional."""
        from lms.lms.ceu_user_type import get_user_type

        plan = self._get_or_create_plan("Professional")
        frappe.get_doc({
            "doctype": "CEU Membership",
            "member": "Administrator",
            "plan": plan,
            "membership_type": "Professional",
            "status": "Active",
            "start_date": today(),
            "end_date": add_years(today(), 1),
        }).insert(ignore_permissions=True)

        result = get_user_type("Administrator")
        self.assertEqual(result["type"], "professional")
        self.assertIn("membership", result)

    def test_returns_company_when_active_company_member(self):
        """User who is an active Company Member returns company type."""
        from lms.lms.ceu_user_type import get_user_type

        company = frappe.get_doc({
            "doctype": "Company Account",
            "company_name": "Test_UT_Company_Type",
            "members": [{"user": "Administrator", "status": "Active"}],
        }).insert(ignore_permissions=True)

        result = get_user_type("Administrator")
        self.assertEqual(result["type"], "company")
        self.assertEqual(result["company"], company.name)

    def test_company_takes_priority_over_professional(self):
        """Company membership is checked first and takes priority."""
        from lms.lms.ceu_user_type import get_user_type

        # Create both professional membership and company membership
        plan = self._get_or_create_plan("Professional")
        frappe.get_doc({
            "doctype": "CEU Membership",
            "member": "Administrator",
            "plan": plan,
            "membership_type": "Professional",
            "status": "Active",
            "start_date": today(),
            "end_date": add_years(today(), 1),
        }).insert(ignore_permissions=True)

        frappe.get_doc({
            "doctype": "Company Account",
            "company_name": "Test_UT_Priority_Co",
            "members": [{"user": "Administrator", "status": "Active"}],
        }).insert(ignore_permissions=True)

        result = get_user_type("Administrator")
        self.assertEqual(result["type"], "company")

    def test_uses_session_user_when_no_user_arg(self):
        """Falls back to frappe.session.user when user arg is None."""
        from lms.lms.ceu_user_type import get_user_type
        # Administrator is the session user in test context
        result = get_user_type()
        # Should return something valid (one_off if no memberships)
        self.assertIn(result["type"], ("one_off", "professional", "company"))

    def _get_or_create_plan(self, plan_type):
        """Get or create a test membership plan."""
        name = f"Test {plan_type} Plan"
        if not frappe.db.exists("CEU Membership Plan", name):
            frappe.get_doc({
                "doctype": "CEU Membership Plan",
                "title": name,
                "plan_type": plan_type,
                "ceu_hours": 50,
                "price": 199,
            }).insert(ignore_permissions=True)
        return name

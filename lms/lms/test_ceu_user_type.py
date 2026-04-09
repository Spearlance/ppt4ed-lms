import frappe
from frappe.tests import UnitTestCase
from unittest.mock import patch, MagicMock

from lms.lms.ceu_user_type import get_user_type


class TestGetUserType(UnitTestCase):
    """Tests for get_user_type — derives account type from DB relationships."""

    def test_returns_one_off_when_no_memberships(self):
        """User with no company or professional memberships is one_off."""
        with patch("lms.lms.ceu_user_type.frappe.db.get_value", return_value=None):
            with patch("lms.lms.ceu_user_type.frappe.session") as mock_session:
                mock_session.user = "nobody@example.com"
                result = get_user_type("nobody@example.com")
        self.assertEqual(result["type"], "one_off")
        self.assertNotIn("membership", result)
        self.assertNotIn("company", result)

    def test_returns_professional_when_active_professional_membership(self):
        """User with active Professional CEU Membership is professional."""
        def mock_get_value(doctype, filters, fieldname, *args, **kwargs):
            if doctype == "Company Member":
                return None
            if doctype == "CEU Membership":
                return "MEM-001"
            return None

        with patch("lms.lms.ceu_user_type.frappe.db.get_value", side_effect=mock_get_value):
            result = get_user_type("pro@example.com")

        self.assertEqual(result["type"], "professional")
        self.assertEqual(result["membership"], "MEM-001")
        self.assertNotIn("company", result)

    def test_returns_company_when_active_company_member(self):
        """User who is an active Company Member returns company type."""
        mock_company = MagicMock()
        mock_company.name = "ACME Corp"
        mock_company.membership = "MEM-CORP-001"

        def mock_get_value(doctype, filters, fieldname, *args, **kwargs):
            if doctype == "Company Member":
                return {"parent": "ACME Corp"}
            return None

        with patch("lms.lms.ceu_user_type.frappe.db.get_value", side_effect=mock_get_value):
            with patch("lms.lms.ceu_user_type.frappe.get_doc", return_value=mock_company):
                result = get_user_type("corp@example.com")

        self.assertEqual(result["type"], "company")
        self.assertEqual(result["company"], "ACME Corp")
        self.assertEqual(result["membership"], "MEM-CORP-001")

    def test_company_takes_priority_over_professional(self):
        """Company membership is checked first and takes priority."""
        mock_company = MagicMock()
        mock_company.name = "BigCo"
        mock_company.membership = "MEM-BIG-001"

        def mock_get_value(doctype, filters, fieldname, *args, **kwargs):
            if doctype == "Company Member":
                return {"parent": "BigCo"}
            if doctype == "CEU Membership":
                return "MEM-PRO-001"
            return None

        with patch("lms.lms.ceu_user_type.frappe.db.get_value", side_effect=mock_get_value):
            with patch("lms.lms.ceu_user_type.frappe.get_doc", return_value=mock_company):
                result = get_user_type("both@example.com")

        self.assertEqual(result["type"], "company")

    def test_uses_session_user_when_no_user_arg(self):
        """Falls back to frappe.session.user when user arg is None."""
        with patch("lms.lms.ceu_user_type.frappe.db.get_value", return_value=None) as mock_db:
            with patch("lms.lms.ceu_user_type.frappe.session") as mock_session:
                mock_session.user = "session@example.com"
                result = get_user_type()

        self.assertEqual(result["type"], "one_off")
        # Verify Company Member query used session user
        first_call_filters = mock_db.call_args_list[0][0][1]
        self.assertEqual(first_call_filters["user"], "session@example.com")

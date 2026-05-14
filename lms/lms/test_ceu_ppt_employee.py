import frappe
from frappe.tests import UnitTestCase
from frappe.utils import today, add_years


class TestPPTEmployee(UnitTestCase):
    def _ensure_plan(self):
        if not frappe.db.exists("CEU Membership Plan", "PPT Employee Test Plan"):
            frappe.get_doc({
                "doctype": "CEU Membership Plan",
                "title": "PPT Employee Test Plan",
                "plan_type": "PPT Employee",
                "ceu_hours": 0,
                "price": 0,
                "active": 1,
            }).insert(ignore_permissions=True)

    def _create_membership(self):
        self._ensure_plan()
        return frappe.get_doc({
            "doctype": "CEU Membership",
            "member": "Administrator",
            "plan": "PPT Employee Test Plan",
            "membership_type": "PPT Employee",
            "status": "Active",
            "start_date": today(),
            "end_date": add_years(today(), 1),
            "credit_balance": 0,
        }).insert(ignore_permissions=True)

    def test_can_create_ppt_employee_plan(self):
        if frappe.db.exists("CEU Membership Plan", "PPT Employee Test Plan"):
            frappe.delete_doc("CEU Membership Plan", "PPT Employee Test Plan", force=True, ignore_permissions=True)

        doc = frappe.get_doc({
            "doctype": "CEU Membership Plan",
            "title": "PPT Employee Test Plan",
            "plan_type": "PPT Employee",
            "ceu_hours": 0,
            "price": 0,
            "active": 1,
        })
        doc.insert(ignore_permissions=True)
        self.assertEqual(doc.plan_type, "PPT Employee")
        self.assertEqual(doc.ceu_hours, 0)

    def test_can_create_ppt_employee_membership(self):
        membership = self._create_membership()
        self.assertEqual(membership.membership_type, "PPT Employee")

    def test_enroll_ppt_employee_sends_verification(self):
        """Enrolling a PPT employee should send a verification email, not enroll directly."""
        from lms.lms.ceu_enrollment import enroll_ppt_employee

        membership = self._create_membership()

        courses = frappe.db.get_all("LMS Course", limit=1)
        if not courses:
            self.skipTest("No LMS Course exists for testing")

        course_name = courses[0].name

        for e in frappe.db.get_all("LMS Enrollment", {"course": course_name, "member": "Administrator"}):
            frappe.delete_doc("LMS Enrollment", e.name, force=True, ignore_permissions=True)

        result = enroll_ppt_employee(course_name, membership.name)

        self.assertEqual(result["status"], "verification_sent")

        # Should NOT be enrolled yet
        self.assertFalse(frappe.db.exists("LMS Enrollment", {
            "member": "Administrator",
            "course": course_name,
        }))

        # Should have a pending verification
        self.assertTrue(frappe.db.exists("PPT Enrollment Verification", {
            "user": "Administrator",
            "course": course_name,
            "status": "Pending",
        }))

    def test_verify_ppt_enrollment_completes_enrollment(self):
        """Clicking the verification link should create the enrollment and ledger entry."""
        from lms.lms.ceu_enrollment import enroll_ppt_employee, verify_ppt_enrollment

        membership = self._create_membership()

        courses = frappe.db.get_all("LMS Course", limit=1)
        if not courses:
            self.skipTest("No LMS Course exists for testing")

        course_name = courses[0].name

        for e in frappe.db.get_all("LMS Enrollment", {"course": course_name, "member": "Administrator"}):
            frappe.delete_doc("LMS Enrollment", e.name, force=True, ignore_permissions=True)

        enroll_ppt_employee(course_name, membership.name)

        verification = frappe.get_last_doc("PPT Enrollment Verification", filters={
            "user": "Administrator",
            "course": course_name,
            "status": "Pending",
        })

        verify_ppt_enrollment(verification.token)

        # Should be enrolled now
        self.assertTrue(frappe.db.exists("LMS Enrollment", {
            "member": "Administrator",
            "course": course_name,
            "credit_source": "PPT Employee",
        }))

        # Should have a ledger entry with hours=0
        ledger = frappe.get_last_doc("CEU Credit Ledger", filters={
            "membership": membership.name,
            "transaction_type": "Enrollment",
            "course": course_name,
        })
        self.assertEqual(ledger.hours, 0)
        self.assertIn("PPT Employee", ledger.notes or "")

        # Verification should be marked as Verified
        verification.reload()
        self.assertEqual(verification.status, "Verified")

    def test_invite_ppt_domain_auto_mints_membership(self):
        """Inviting a @ppt4kids.com email auto-mints a PPT Employee membership
        and ignores any company arg passed alongside."""
        from unittest.mock import patch
        from lms.lms.api import invite_lms_member

        email = "test-ppt-invite@ppt4kids.com"
        for m in frappe.get_all("CEU Membership", filters={"member": email}):
            frappe.delete_doc("CEU Membership", m.name, force=True, ignore_permissions=True)
        if frappe.db.exists("User", email):
            frappe.delete_doc("User", email, force=True, ignore_permissions=True)

        with patch("lms.lms.api.lms_send_template_mail"):
            result = invite_lms_member(
                email=email,
                first_name="Test",
                last_name="PPT",
                roles=["LMS Student"],
                company="Some Fake Company",
            )

        self.assertEqual(result["user"], email)

        membership = frappe.db.get_value(
            "CEU Membership",
            {"member": email, "membership_type": "PPT Employee", "status": "Active"},
            ["name", "credit_balance"],
            as_dict=True,
        )
        self.assertIsNotNone(membership, "Expected PPT Employee membership to be auto-minted")
        self.assertEqual(membership.credit_balance, 0)

        company_member = frappe.db.exists(
            "Company Member",
            {"user": email, "parent": "Some Fake Company"},
        )
        self.assertFalse(company_member, "PPT employee should not be added to any company")

    def test_invite_non_ppt_domain_skips_membership_mint(self):
        """Non-PPT emails should NOT get an auto-minted PPT Employee membership."""
        from unittest.mock import patch
        from lms.lms.api import invite_lms_member

        email = "test-civilian-invite@example.com"
        if frappe.db.exists("User", email):
            frappe.delete_doc("User", email, force=True, ignore_permissions=True)

        with patch("lms.lms.api.lms_send_template_mail"):
            invite_lms_member(
                email=email,
                first_name="Test",
                last_name="Civilian",
                roles=["LMS Student"],
            )

        self.assertFalse(frappe.db.exists(
            "CEU Membership",
            {"member": email, "membership_type": "PPT Employee"},
        ), "Non-PPT email should not get a PPT Employee membership")

    def test_inactive_membership_blocks_enrollment(self):
        """PPT employee with inactive membership cannot enroll."""
        from lms.lms.ceu_enrollment import enroll_ppt_employee

        membership = self._create_membership()
        membership.status = "Cancelled"
        membership.save(ignore_permissions=True)

        courses = frappe.db.get_all("LMS Course", limit=1)
        if not courses:
            self.skipTest("No LMS Course exists for testing")

        with self.assertRaises(frappe.exceptions.ValidationError):
            enroll_ppt_employee(courses[0].name, membership.name)

    def test_expired_token_blocks_enrollment(self):
        """An expired verification token should not complete enrollment."""
        from lms.lms.ceu_enrollment import enroll_ppt_employee, verify_ppt_enrollment
        from frappe.utils import add_to_date, now_datetime

        membership = self._create_membership()

        courses = frappe.db.get_all("LMS Course", limit=1)
        if not courses:
            self.skipTest("No LMS Course exists for testing")

        course_name = courses[0].name

        for e in frappe.db.get_all("LMS Enrollment", {"course": course_name, "member": "Administrator"}):
            frappe.delete_doc("LMS Enrollment", e.name, force=True, ignore_permissions=True)

        enroll_ppt_employee(course_name, membership.name)

        verification = frappe.get_last_doc("PPT Enrollment Verification", filters={
            "user": "Administrator",
            "course": course_name,
            "status": "Pending",
        })

        # Force-expire the token
        frappe.db.set_value(
            "PPT Enrollment Verification", verification.name,
            "expires_on", add_to_date(now_datetime(), minutes=-1),
        )

        with self.assertRaises(frappe.exceptions.ValidationError):
            verify_ppt_enrollment(verification.token)

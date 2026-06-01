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

    def test_enroll_ppt_employee_enrolls_directly(self):
        """PPT employees enroll instantly — no verification email, immediate
        LMS Enrollment + zero-hour ledger entry."""
        from lms.lms.ceu_enrollment import enroll_ppt_employee

        membership = self._create_membership()

        courses = frappe.db.get_all("LMS Course", limit=1)
        if not courses:
            self.skipTest("No LMS Course exists for testing")

        course_name = courses[0].name

        for e in frappe.db.get_all("LMS Enrollment", {"course": course_name, "member": "Administrator"}):
            frappe.delete_doc("LMS Enrollment", e.name, force=True, ignore_permissions=True)

        result = enroll_ppt_employee(course_name, membership.name)

        self.assertEqual(result["status"], "enrolled")
        self.assertTrue(frappe.db.exists("LMS Enrollment", {
            "member": "Administrator",
            "course": course_name,
            "credit_source": "PPT Employee",
        }))

        ledger = frappe.get_last_doc("CEU Credit Ledger", filters={
            "membership": membership.name,
            "transaction_type": "Enrollment",
            "course": course_name,
        })
        self.assertEqual(ledger.hours, 0)
        self.assertIn("PPT Employee", ledger.notes or "")

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

    def _delete_user_state(self, email):
        for r in frappe.get_all("LMS Event Registration", filters={"member": email}):
            frappe.delete_doc("LMS Event Registration", r.name, force=True, ignore_permissions=True)
        for e in frappe.get_all("LMS Enrollment", filters={"member": email}):
            frappe.delete_doc("LMS Enrollment", e.name, force=True, ignore_permissions=True)
        for m in frappe.get_all("CEU Membership", filters={"member": email}):
            frappe.delete_doc("CEU Membership", m.name, force=True, ignore_permissions=True)
        if frappe.db.exists("User", email):
            frappe.delete_doc("User", email, force=True, ignore_permissions=True)

    def _ensure_paid_event(self, title="PPT Test Paid Event"):
        existing = frappe.db.exists("LMS Event", {"title": title})
        if existing:
            event = frappe.get_doc("LMS Event", existing)
        else:
            event = frappe.get_doc({
                "doctype": "LMS Event",
                "title": title,
                "start_date": today(),
                "end_date": today(),
                "start_time": "09:00:00",
                "end_time": "11:00:00",
                "timezone": "America/New_York",
                "description": "Test paid event for PPT employee signup flow.",
            })
        event.published = 1
        event.paid_event = 1
        event.amount = 100
        event.amount_usd = 100
        event.currency = "USD"
        event.save(ignore_permissions=True)
        return event.name

    def _ensure_paid_course(self, title="PPT Test Paid Course"):
        existing = frappe.db.exists("LMS Course", {"title": title})
        if existing:
            course = frappe.get_doc("LMS Course", existing)
        else:
            course = frappe.get_doc({
                "doctype": "LMS Course",
                "title": title,
                "short_introduction": "Paid course for PPT employee signup test.",
                "description": "Test paid course.",
                "instructors": [{"instructor": "Administrator"}],
            })
        course.published = 1
        course.paid_course = 1
        course.course_price = 100
        course.amount_usd = 100
        course.currency = "USD"
        course.save(ignore_permissions=True)
        return course.name

    def test_user_after_insert_mints_ppt_membership(self):
        """Creating a User with a PPT-domain email triggers User.after_insert,
        which mints the PPT Employee membership automatically. This is the
        centralized guard that protects every signup path (public, legacy,
        Desk) without each one needing to call the mint helper itself."""
        email = "test-after-insert@ppt4kids.com"
        self._delete_user_state(email)

        user = frappe.get_doc({
            "doctype": "User",
            "email": email,
            "first_name": "After",
            "last_name": "Insert",
            "enabled": 1,
            "send_welcome_email": 0,
            "user_type": "Website User",
        })
        user.flags.ignore_permissions = True
        user.insert()

        self.assertTrue(
            frappe.db.exists(
                "CEU Membership",
                {"member": email, "membership_type": "PPT Employee", "status": "Active"},
            ),
            "Expected User.after_insert to auto-mint a PPT Employee membership",
        )

    def test_user_after_insert_skips_non_ppt_email(self):
        """Non-PPT-domain user creation must NOT mint a PPT Employee membership."""
        email = "test-non-ppt-after-insert@example.com"
        self._delete_user_state(email)

        user = frappe.get_doc({
            "doctype": "User",
            "email": email,
            "first_name": "Non",
            "last_name": "PPT",
            "enabled": 1,
            "send_welcome_email": 0,
            "user_type": "Website User",
        })
        user.flags.ignore_permissions = True
        user.insert()

        self.assertFalse(frappe.db.exists(
            "CEU Membership",
            {"member": email, "membership_type": "PPT Employee"},
        ))

    def test_signup_and_enroll_paid_event_ppt_employee_skips_checkout(self):
        """Public signup from a paid event landing page with a PPT email must
        free-enroll instead of returning a Stripe checkout URL. This is the
        regression that prompted the audit — pre-fix, PPT staff got the paywall."""
        from lms.lms.api import signup_and_enroll

        event_name = self._ensure_paid_event()
        email = "test-signup-ppt-event@ppt4kids.com"
        self._delete_user_state(email)

        original_user = frappe.session.user
        try:
            result = signup_and_enroll(
                email=email,
                password="testpass1234",
                full_name="Test PPT Event",
                target_type="event",
                target_slug=event_name,
                intent="paid",
            )
        finally:
            frappe.set_user(original_user)

        self.assertEqual(result["status"], "logged_in")
        self.assertEqual(result["redirect_to"], f"/lms/events/{event_name}")
        self.assertTrue(frappe.db.exists("LMS Event Registration", {
            "event": event_name,
            "member": email,
            "credit_source": "PPT Employee",
        }), "Expected free PPT-employee registration with credit_source set")

    def test_signup_and_enroll_paid_course_ppt_employee_skips_checkout(self):
        """Same as the event flow, for paid courses."""
        from lms.lms.api import signup_and_enroll

        course_name = self._ensure_paid_course()
        email = "test-signup-ppt-course@ppt4kids.com"
        self._delete_user_state(email)

        original_user = frappe.session.user
        try:
            result = signup_and_enroll(
                email=email,
                password="testpass1234",
                full_name="Test PPT Course",
                target_type="course",
                target_slug=course_name,
                intent="paid",
            )
        finally:
            frappe.set_user(original_user)

        self.assertEqual(result["status"], "logged_in")
        self.assertEqual(result["redirect_to"], f"/lms/courses/{course_name}")
        self.assertTrue(frappe.db.exists("LMS Enrollment", {
            "course": course_name,
            "member": email,
            "credit_source": "PPT Employee",
        }), "Expected free PPT-employee enrollment with credit_source set")

    def test_create_event_checkout_blocks_ppt_employee(self):
        """Belt-and-suspenders: even if a PPT employee somehow reaches the
        Stripe checkout endpoint (stale tab, future regression), it must
        refuse rather than charging them."""
        from lms.lms.ceu_stripe import create_event_checkout

        event_name = self._ensure_paid_event(title="PPT Checkout Guard Event")
        email = "test-checkout-guard-event@ppt4kids.com"
        self._delete_user_state(email)
        frappe.get_doc({
            "doctype": "User", "email": email, "first_name": "Guard",
            "last_name": "Event", "enabled": 1, "send_welcome_email": 0,
            "user_type": "Website User",
        }).insert(ignore_permissions=True)

        original_user = frappe.session.user
        try:
            frappe.set_user(email)
            with self.assertRaises(frappe.exceptions.ValidationError):
                create_event_checkout(event_name)
        finally:
            frappe.set_user(original_user)

    def test_create_one_off_checkout_blocks_ppt_employee(self):
        """Same guard for course checkout."""
        from lms.lms.ceu_stripe import create_one_off_checkout

        course_name = self._ensure_paid_course(title="PPT Checkout Guard Course")
        email = "test-checkout-guard-course@ppt4kids.com"
        self._delete_user_state(email)
        frappe.get_doc({
            "doctype": "User", "email": email, "first_name": "Guard",
            "last_name": "Course", "enabled": 1, "send_welcome_email": 0,
            "user_type": "Website User",
        }).insert(ignore_permissions=True)

        original_user = frappe.session.user
        try:
            frappe.set_user(email)
            with self.assertRaises(frappe.exceptions.ValidationError):
                create_one_off_checkout(course_name)
        finally:
            frappe.set_user(original_user)


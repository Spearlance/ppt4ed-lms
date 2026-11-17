"""Edit Profile saves: members edit themselves, LMS admins edit anyone, and
only the dialog's own fields are ever writable."""

from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from lms.lms.profile import update_profile

MEMBER = "garrett.test.profile1@example.com"
OTHER = "garrett.test.profile2@example.com"
ADMIN = "garrett.test.profile3@example.com"


class TestProfileUpdate(UnitTestCase):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		self._patch = patch("lms.lms.user.queue_signup_webhook")
		self._patch.start()
		self._cleanup()
		self._make_user(MEMBER, "One", ["LMS Student"])
		self._make_user(OTHER, "Two", ["LMS Student"])
		self._make_user(ADMIN, "Three", ["LMS Student", "Moderator"])

	def tearDown(self):
		frappe.set_user("Administrator")
		self._cleanup()
		self._patch.stop()
		super().tearDown()

	def _make_user(self, email, last_name, roles):
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "Garrett",
				"last_name": f"Profile {last_name}",
				"send_welcome_email": 0,
			}
		)
		user.flags.no_welcome_mail = True
		user.insert(ignore_permissions=True)
		user.add_roles(*roles)

	def _cleanup(self):
		for email in (MEMBER, OTHER, ADMIN):
			if frappe.db.exists("User", email):
				frappe.delete_doc("User", email, ignore_permissions=True, force=True)

	def test_member_edits_own_profile(self):
		frappe.set_user(MEMBER)
		saved = update_profile(
			user=MEMBER,
			fields={"first_name": " Gary ", "last_name": "Tester", "headline": "Pediatric PT"},
		)
		self.assertEqual(saved["full_name"], "Gary Tester")
		self.assertEqual(frappe.db.get_value("User", MEMBER, "headline"), "Pediatric PT")

	def test_admin_edits_someone_else(self):
		frappe.set_user(ADMIN)
		update_profile(
			user=MEMBER,
			fields={
				"bio": "<p>Instructor bio</p>",
				"license_type": "PT",
				"license_state": "FL",
				"professional_license_number": "PT12345",
				"signature_text": "G. Tester",
				"credentials": "PT, DPT",
			},
		)
		row = frappe.db.get_value(
			"User",
			MEMBER,
			["bio", "license_type", "license_state", "signature_text", "credentials", "enabled"],
			as_dict=True,
		)
		self.assertIn("Instructor bio", row.bio)
		self.assertEqual(
			(row.license_type, row.license_state, row.signature_text, row.credentials),
			("PT", "FL", "G. Tester", "PT, DPT"),
		)
		self.assertEqual(row.enabled, 1)
		# Fields that were not sent are left alone.
		self.assertEqual(frappe.db.get_value("User", MEMBER, "first_name"), "Garrett")

	def test_member_cannot_edit_someone_else(self):
		frappe.set_user(MEMBER)
		with self.assertRaises(frappe.PermissionError):
			update_profile(user=OTHER, fields={"headline": "Nope"})
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			update_profile(user=OTHER, fields={"headline": "Nope"})
		frappe.set_user("Administrator")
		self.assertFalse(frappe.db.get_value("User", OTHER, "headline"))

	def test_only_profile_fields_are_writable(self):
		frappe.set_user(ADMIN)
		for fields in (
			{"email": "hijack@example.com"},
			{"enabled": "0"},
			{"new_password": "Sneaky@12345"},
			{"roles": "System Manager"},
			{"headline": "ok", "username": "taken"},
		):
			with self.assertRaises(frappe.ValidationError):
				update_profile(user=MEMBER, fields=fields)
		frappe.set_user("Administrator")
		self.assertFalse(frappe.db.get_value("User", MEMBER, "headline"))
		self.assertNotIn("System Manager", frappe.get_roles(MEMBER))

	def test_validation(self):
		frappe.set_user(ADMIN)
		with self.assertRaises(frappe.ValidationError):
			update_profile(user=MEMBER, fields={"first_name": "  "})
		with self.assertRaises(frappe.ValidationError):
			update_profile(user=MEMBER, fields={"credentials": "x" * 141})
		with self.assertRaises(frappe.DoesNotExistError):
			update_profile(user="garrett.test.nobody@example.com", fields={"headline": "x"})

	def test_built_in_accounts_are_protected(self):
		frappe.set_user(ADMIN)
		with self.assertRaises(frappe.PermissionError):
			update_profile(user="Administrator", fields={"headline": "Nope"})

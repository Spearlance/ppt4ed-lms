"""Private registration link: an unlisted link that lets a prepaid group
register for an unpublished event.

Covers the code gate (wrong / reset / disabled links all fail the same way),
free registration through the link, the license gate, closed states, the
admin on/off/reset endpoints, and the admin "Enroll" endpoint.
"""

from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase
from frappe.utils import add_days, today

from lms.lms.event_private_link import (
	get_private_link,
	get_private_registration_info,
	private_link_code,
	register_member,
	register_with_private_link,
	set_private_link,
)
from lms.lms.license import LicenseRequiredError
from lms.lms.utils import get_event_details

REG_MODULE = "lms.lms.doctype.lms_event_registration.lms_event_registration"
TITLE_PREFIX = "Garrett Test Private Link"
LICENSED = "garrett.test.privatelink1@example.com"
UNLICENSED = "garrett.test.privatelink2@example.com"


class TestEventPrivateLink(UnitTestCase):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		self._patches = [
			patch(f"{REG_MODULE}.send_confirmation_email"),
			patch(f"{REG_MODULE}.queue_signup_webhook"),
			patch("lms.lms.user.queue_signup_webhook"),
		]
		for p in self._patches:
			p.start()

		self._cleanup()
		self.licensed = self._make_user(LICENSED, 1)
		frappe.db.set_value(
			"User",
			self.licensed,
			{
				"license_type": "PT",
				"license_state": "FL",
				"professional_license_number": "PT12345",
			},
		)
		self.unlicensed = self._make_user(UNLICENSED, 2)
		self.event = self._make_event("A")
		self.code = self._enable(self.event)

	def tearDown(self):
		frappe.set_user("Administrator")
		self._cleanup()
		for p in self._patches:
			p.stop()
		super().tearDown()

	# ------------------------------------------------------------------ fixtures

	def _make_user(self, email, n):
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "Garrett",
				"last_name": f"Private Link {n}",
				"send_welcome_email": 0,
			}
		)
		user.flags.no_welcome_mail = True
		user.insert(ignore_permissions=True)
		user.add_roles("LMS Student")
		return user.name

	def _make_event(self, suffix, **overrides):
		day = add_days(today(), 30)
		values = {
			"doctype": "LMS Event",
			"title": f"{TITLE_PREFIX} {suffix}",
			"start_date": day,
			"end_date": day,
			"start_time": "09:00:00",
			"end_time": "11:00:00",
			"timezone": "America/New_York",
			"description": "Private link test event.",
			"event_details": "Private link test event.",
			"instructors": [{"instructor": "Administrator"}],
			"published": 0,
			"allow_self_enrollment": 0,
		}
		values.update(overrides)
		event = frappe.get_doc(values)
		event.insert(ignore_permissions=True)
		return event.name

	def _enable(self, event):
		url = set_private_link(event=event, enabled=1)["url"]
		return url.rsplit("/", 1)[-1]

	def _registered(self, user, event=None):
		return bool(
			frappe.db.exists("LMS Event Registration", {"event": event or self.event, "member": user})
		)

	def _cleanup(self):
		for event in frappe.get_all("LMS Event", {"title": ["like", f"{TITLE_PREFIX}%"]}, pluck="name"):
			frappe.db.delete("LMS Event Registration", {"event": event})
			frappe.db.delete("Comment", {"reference_doctype": "LMS Event", "reference_name": event})
			frappe.delete_doc("LMS Event", event, ignore_permissions=True, force=True)
		for email in (LICENSED, UNLICENSED):
			if frappe.db.exists("User", email):
				frappe.delete_doc("User", email, ignore_permissions=True, force=True)

	# --------------------------------------------------------------------- link

	def test_link_points_at_join_page_and_code_is_not_stored(self):
		state = get_private_link(event=self.event)
		self.assertTrue(state["enabled"])
		self.assertTrue(state["url"].endswith(f"/events/{self.event}/join/{self.code}"))
		self.assertEqual(self.code, private_link_code(self.event, 0))
		stored = frappe.get_doc("LMS Event", self.event).as_dict()
		self.assertNotIn(self.code, frappe.as_json(stored))

	def test_guest_sees_event_with_valid_code_only(self):
		frappe.set_user("Guest")
		info = get_private_registration_info(event=self.event, code=self.code)
		self.assertEqual(info["title"], f"{TITLE_PREFIX} A")
		self.assertFalse(info["logged_in"])
		self.assertFalse(info["registered"])
		self.assertIsNone(info["closed_reason"])
		for bad in ("", "nope", self.code[:-1] + ("0" if self.code[-1] != "0" else "1")):
			with self.assertRaises(frappe.PermissionError):
				get_private_registration_info(event=self.event, code=bad)
		with self.assertRaises(frappe.PermissionError):
			get_private_registration_info(event="no-such-event", code=self.code)

	def test_reset_and_turn_off_kill_the_old_link(self):
		new_url = set_private_link(event=self.event, enabled=1, reset=1)["url"]
		new_code = new_url.rsplit("/", 1)[-1]
		self.assertNotEqual(new_code, self.code)
		frappe.set_user(self.licensed)
		with self.assertRaises(frappe.PermissionError):
			register_with_private_link(event=self.event, code=self.code)
		self.assertFalse(self._registered(self.licensed))

		frappe.set_user("Administrator")
		state = set_private_link(event=self.event, enabled=0)
		self.assertFalse(state["enabled"])
		self.assertIsNone(state["url"])
		frappe.set_user(self.licensed)
		with self.assertRaises(frappe.PermissionError):
			register_with_private_link(event=self.event, code=new_code)

	def test_a_code_only_opens_its_own_event(self):
		other = self._make_event("B")
		self._enable(other)
		frappe.set_user(self.licensed)
		with self.assertRaises(frappe.PermissionError):
			register_with_private_link(event=other, code=self.code)

	# ------------------------------------------------------------- registration

	def test_licensed_user_registers_on_unpublished_event(self):
		frappe.set_user(self.licensed)
		# Before registering, the unpublished event is invisible to them.
		self.assertFalse(get_event_details(self.event))
		result = register_with_private_link(event=self.event, code=self.code)
		self.assertEqual(result["status"], "registered")
		self.assertTrue(self._registered(self.licensed))
		self.assertEqual(get_event_details(self.event).get("name"), self.event)
		# Idempotent.
		again = register_with_private_link(event=self.event, code=self.code)
		self.assertTrue(again["already_registered"])
		self.assertEqual(
			frappe.db.count("LMS Event Registration", {"event": self.event, "member": self.licensed}), 1
		)
		info = get_private_registration_info(event=self.event, code=self.code)
		self.assertTrue(info["registered"])

	def test_guest_cannot_register(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.AuthenticationError):
			register_with_private_link(event=self.event, code=self.code)

	def test_license_is_required(self):
		frappe.set_user(self.unlicensed)
		with self.assertRaises(LicenseRequiredError):
			register_with_private_link(event=self.event, code=self.code)
		self.assertFalse(self._registered(self.unlicensed))

	def test_without_the_link_self_registration_stays_closed(self):
		frappe.set_user(self.licensed)
		doc = frappe.get_doc(
			{"doctype": "LMS Event Registration", "event": self.event, "member": self.licensed}
		)
		with self.assertRaises(frappe.ValidationError):
			doc.insert(ignore_permissions=True)

	def test_full_ended_and_paid_events_are_closed(self):
		full = self._make_event("Full", seat_count=1)
		full_code = self._enable(full)
		frappe.get_doc(
			{"doctype": "LMS Event Registration", "event": full, "member": self.unlicensed}
		).insert(ignore_permissions=True)

		past_day = add_days(today(), -2)
		ended = self._make_event("Ended", start_date=past_day, end_date=past_day)
		ended_code = self._enable(ended)

		frappe.set_user(self.licensed)
		for event, code in ((full, full_code), (ended, ended_code)):
			self.assertTrue(get_private_registration_info(event=event, code=code)["closed_reason"])
			with self.assertRaises(frappe.ValidationError):
				register_with_private_link(event=event, code=code)
			self.assertFalse(self._registered(self.licensed, event))

		frappe.set_user("Administrator")
		paid = self._make_event("Paid", paid_event=1, amount=50)
		with self.assertRaises(frappe.ValidationError):
			set_private_link(event=paid, enabled=1)

	# -------------------------------------------------------------------- admin

	def test_only_event_admins_manage_the_link(self):
		frappe.set_user(self.licensed)
		with self.assertRaises(frappe.PermissionError):
			get_private_link(event=self.event)
		with self.assertRaises(frappe.PermissionError):
			set_private_link(event=self.event, enabled=0)
		with self.assertRaises(frappe.PermissionError):
			register_member(event=self.event, member=self.licensed)

	def test_admin_enrolls_a_member(self):
		result = register_member(event=self.event, member=self.unlicensed)
		self.assertEqual(result["status"], "registered")
		self.assertTrue(self._registered(self.unlicensed))
		with self.assertRaises(frappe.ValidationError):
			register_member(event=self.event, member=self.unlicensed)
		with self.assertRaises(frappe.ValidationError):
			register_member(event=self.event, member="nobody@example.com")

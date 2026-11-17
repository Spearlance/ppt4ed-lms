"""Guarded event deletion.

An event with attendee data (registrations, payments, certificates, ...) must
never be deletable; only empty events can go. Both the current endpoint and
the legacy `delete_batch` name are covered.
"""

from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase
from frappe.utils import add_days, today

from lms.lms.api import delete_batch, delete_event, get_event_delete_blockers

REG_MODULE = "lms.lms.doctype.lms_event_registration.lms_event_registration"
TITLE_PREFIX = "Garrett Test Event Delete"
ATTENDEE = "garrett.test.eventdelete1@example.com"


class TestEventDelete(UnitTestCase):
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
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": ATTENDEE,
				"first_name": "Garrett",
				"last_name": "Event Delete",
				"send_welcome_email": 0,
			}
		)
		user.flags.no_welcome_mail = True
		user.insert(ignore_permissions=True)
		user.add_roles("LMS Student")
		self.attendee = user.name

	def tearDown(self):
		frappe.set_user("Administrator")
		self._cleanup()
		for p in self._patches:
			p.stop()
		super().tearDown()

	def _make_event(self, suffix):
		day = add_days(today(), 30)
		event = frappe.get_doc(
			{
				"doctype": "LMS Event",
				"title": f"{TITLE_PREFIX} {suffix}",
				"start_date": day,
				"end_date": day,
				"start_time": "09:00:00",
				"end_time": "11:00:00",
				"timezone": "America/New_York",
				"description": "Event delete test event.",
				"event_details": "Event delete test event.",
				"instructors": [{"instructor": "Administrator"}],
				"published": 0,
			}
		)
		event.insert(ignore_permissions=True)
		return event.name

	def _register(self, event):
		frappe.get_doc(
			{"doctype": "LMS Event Registration", "event": event, "member": self.attendee}
		).insert(ignore_permissions=True)

	def _cleanup(self):
		# Only ever touches this test's own fixtures, matched by title prefix.
		for event in frappe.get_all("LMS Event", {"title": ["like", f"{TITLE_PREFIX}%"]}, pluck="name"):
			frappe.db.delete("LMS Event Registration", {"event": event})
			frappe.delete_doc("LMS Event", event, ignore_permissions=True, force=True)
		if frappe.db.exists("User", ATTENDEE):
			frappe.delete_doc("User", ATTENDEE, ignore_permissions=True, force=True)

	def test_empty_event_is_deleted(self):
		event = self._make_event("Empty")
		self.assertEqual(get_event_delete_blockers(event), [])
		delete_event(event=event)
		self.assertFalse(frappe.db.exists("LMS Event", event))

	def test_event_with_registrations_is_refused_and_untouched(self):
		event = self._make_event("Registered")
		self._register(event)

		with self.assertRaises(frappe.ValidationError) as raised:
			delete_event(event=event)
		self.assertIn("1 registered attendee(s)", str(raised.exception))

		self.assertTrue(frappe.db.exists("LMS Event", event))
		self.assertEqual(frappe.db.count("LMS Event Registration", {"event": event}), 1)

	def test_legacy_delete_batch_is_guarded_too(self):
		event = self._make_event("Legacy")
		self._register(event)
		with self.assertRaises(frappe.ValidationError):
			delete_batch(batch=event)
		self.assertTrue(frappe.db.exists("LMS Event", event))
		self.assertEqual(frappe.db.count("LMS Event Registration", {"event": event}), 1)

	def test_students_and_guests_cannot_delete(self):
		event = self._make_event("Permission")
		for user in (self.attendee, "Guest"):
			frappe.set_user(user)
			with self.assertRaises(frappe.PermissionError):
				delete_event(event=event)
		frappe.set_user("Administrator")
		self.assertTrue(frappe.db.exists("LMS Event", event))

	def test_missing_event_is_reported(self):
		with self.assertRaises(frappe.DoesNotExistError):
			delete_event(event="garrett-test-no-such-event")

"""Cancelling an event: unpublish + cancelled notice, email only when asked."""

from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase
from frappe.utils import add_days, today
from frappe.utils.jinja import get_email_from_template

from lms.lms.event_cancel import cancel_event, get_cancel_info, restore_event
from lms.lms.utils import get_event_details

REG_MODULE = "lms.lms.doctype.lms_event_registration.lms_event_registration"
EVENT_MODULE = "lms.lms.doctype.lms_event.lms_event"
TITLE_PREFIX = "Garrett Test Event Cancel"
ATTENDEES = (
	"garrett.test.eventcancel1@example.com",
	"garrett.test.eventcancel2@example.com",
)


class TestEventCancel(UnitTestCase):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		self._patches = [
			patch(f"{REG_MODULE}.send_confirmation_email"),
			patch(f"{REG_MODULE}.queue_signup_webhook"),
			patch("lms.lms.user.queue_signup_webhook"),
			# Publishing an event announces it; never let a test do that.
			patch(f"{EVENT_MODULE}.send_notification_for_published_event"),
		]
		for p in self._patches:
			p.start()
		self.mail = patch("lms.lms.event_cancel.lms_send_template_mail").start()
		self._cleanup()
		for n, email in enumerate(ATTENDEES, 1):
			user = frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": f"Attendee{n}",
					"last_name": "Event Cancel",
					"send_welcome_email": 0,
				}
			)
			user.flags.no_welcome_mail = True
			user.insert(ignore_permissions=True)
			user.add_roles("LMS Student")
		self.event = self._make_event()
		for email in ATTENDEES:
			frappe.get_doc(
				{"doctype": "LMS Event Registration", "event": self.event, "member": email}
			).insert(ignore_permissions=True)

	def tearDown(self):
		frappe.set_user("Administrator")
		self._cleanup()
		patch.stopall()
		super().tearDown()

	def _make_event(self):
		day = add_days(today(), 30)
		with patch("frappe.enqueue"):
			event = frappe.get_doc(
				{
					"doctype": "LMS Event",
					"title": f"{TITLE_PREFIX} A",
					"start_date": day,
					"end_date": day,
					"start_time": "09:00:00",
					"end_time": "11:00:00",
					"timezone": "America/New_York",
					"description": "Event cancel test event.",
					"event_details": "Event cancel test event.",
					"instructors": [{"instructor": "Administrator"}],
					"published": 1,
				}
			)
			event.insert(ignore_permissions=True)
		return event.name

	def _cleanup(self):
		for event in frappe.get_all("LMS Event", {"title": ["like", f"{TITLE_PREFIX}%"]}, pluck="name"):
			frappe.db.delete("LMS Event Registration", {"event": event})
			frappe.delete_doc("LMS Event", event, ignore_permissions=True, force=True)
		for email in ATTENDEES:
			if frappe.db.exists("User", email):
				frappe.delete_doc("User", email, ignore_permissions=True, force=True)

	def _state(self):
		return frappe.db.get_value(
			"LMS Event",
			self.event,
			["cancelled", "published", "cancellation_message", "cancelled_on"],
			as_dict=True,
		)

	def test_cancel_without_email_sends_nothing(self):
		self.assertEqual(get_cancel_info(self.event)["registrations"], 2)
		result = cancel_event(event=self.event, message="  Venue flooded.  ")

		self.assertEqual(result, {"cancelled": 1, "notified": 0})
		self.mail.assert_not_called()
		state = self._state()
		self.assertEqual((state.cancelled, state.published), (1, 0))
		self.assertEqual(state.cancellation_message, "Venue flooded.")
		self.assertTrue(state.cancelled_on)
		# Registrations are kept.
		self.assertEqual(frappe.db.count("LMS Event Registration", {"event": self.event}), 2)

	def test_cancel_with_email_notifies_each_registrant_once(self):
		result = cancel_event(event=self.event, notify="1", message="Venue flooded.")

		self.assertEqual(result["notified"], 2)
		self.assertEqual(self.mail.call_count, 2)
		recipients = sorted(call.kwargs["recipients"] for call in self.mail.call_args_list)
		self.assertEqual(recipients, sorted(ATTENDEES))
		first = self.mail.call_args_list[0].kwargs
		self.assertIn("Cancelled:", first["default_subject"])
		self.assertEqual(first["args"]["message"], "Venue flooded.")
		self.assertEqual(first["args"]["first_name"], "Attendee1")

	def test_one_failed_email_does_not_undo_the_cancellation(self):
		self.mail.side_effect = [Exception("smtp down"), None]
		result = cancel_event(event=self.event, notify=1)
		self.assertEqual(result["notified"], 1)
		self.assertEqual(self._state().cancelled, 1)

	def test_cannot_cancel_twice(self):
		cancel_event(event=self.event, notify=1)
		with self.assertRaises(frappe.ValidationError):
			cancel_event(event=self.event, notify=1)
		self.assertEqual(self.mail.call_count, 2)

	def test_students_and_guests_cannot_cancel_or_restore(self):
		for user in (ATTENDEES[0], "Guest"):
			frappe.set_user(user)
			with self.assertRaises(frappe.PermissionError):
				cancel_event(event=self.event, notify=1)
			with self.assertRaises(frappe.PermissionError):
				restore_event(event=self.event)
		frappe.set_user("Administrator")
		self.assertEqual(self._state().cancelled, 0)
		self.mail.assert_not_called()

	def test_ordinary_save_cannot_uncancel_or_publish(self):
		cancel_event(event=self.event)

		doc = frappe.get_doc("LMS Event", self.event)
		doc.cancelled = 0
		doc.title = f"{TITLE_PREFIX} A renamed"
		doc.save(ignore_permissions=True)
		self.assertEqual(self._state().cancelled, 1)

		doc = frappe.get_doc("LMS Event", self.event)
		doc.published = 1
		with self.assertRaises(frappe.ValidationError):
			doc.save(ignore_permissions=True)
		self.assertEqual(self._state().published, 0)

	def test_ordinary_save_cannot_cancel(self):
		doc = frappe.get_doc("LMS Event", self.event)
		doc.cancelled = 1
		with patch("frappe.enqueue"):
			doc.save(ignore_permissions=True)
		state = self._state()
		self.assertEqual((state.cancelled, state.published), (0, 1))

	def test_restore_leaves_it_unpublished_and_sends_nothing(self):
		cancel_event(event=self.event, message="Venue flooded.")
		self.assertEqual(restore_event(event=self.event), {"cancelled": 0})
		state = self._state()
		self.assertEqual((state.cancelled, state.published), (0, 0))
		self.assertFalse(state.cancellation_message)
		self.mail.assert_not_called()
		with self.assertRaises(frappe.ValidationError):
			restore_event(event=self.event)

	def test_registrant_still_sees_the_event_with_the_notice(self):
		cancel_event(event=self.event, message="Venue flooded.")
		frappe.set_user(ATTENDEES[0])
		details = get_event_details(self.event)
		self.assertEqual(details.cancelled, 1)
		self.assertEqual(details.cancellation_message, "Venue flooded.")

	def test_email_copy(self):
		args = {
			"first_name": "Pat",
			"title": "Turtle Bracing",
			"date": "December 18, 2026",
			"message": "Venue flooded.",
			"paid_event": 1,
		}
		html, _text = get_email_from_template("event_cancelled", args)
		for expected in ("Pat", "Turtle Bracing", "December 18, 2026", "Venue flooded.", "refund"):
			self.assertIn(expected, html)

		html, _text = get_email_from_template("event_cancelled", {**args, "paid_event": 0, "message": ""})
		self.assertNotIn("refund", html)
		self.assertNotIn("Venue flooded.", html)

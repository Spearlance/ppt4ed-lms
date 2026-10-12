from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase
from frappe.utils import today

REG_MODULE = "lms.lms.doctype.lms_event_registration.lms_event_registration"
EVENT_TITLE = "Garrett Test Remove Registrant Event"
EMAILS = (
	"garrett.test.evtremove1@example.com",
	"garrett.test.evtremove2@example.com",
	"garrett.test.evtremove3@example.com",
)


class TestRemoveEventRegistrations(UnitTestCase):
	"""remove_event_registrations: the LMS-side replacement for deleting
	registrations in Desk, which staff can't reach on prod."""

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

		courses = frappe.get_all("LMS Course", limit=1, pluck="name")
		if not courses:
			self.skipTest("No LMS Course exists for testing")
		self.course = courses[0]

		self._cleanup()
		self.users = [self._make_user(email, i) for i, email in enumerate(EMAILS, start=1)]
		self.event = self._make_event(self.course)
		self.other_event = self._make_event(self.course, title=f"{EVENT_TITLE} Other")
		self.regs = [self._register(self.event, u) for u in self.users[:2]]
		self.other_reg = self._register(self.other_event, self.users[2])

	def tearDown(self):
		frappe.set_user("Administrator")
		self._cleanup()
		for p in self._patches:
			p.stop()
		super().tearDown()

	# fixtures

	def _make_user(self, email, n):
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "Garrett",
				"last_name": f"Test {n}",
				"send_welcome_email": 0,
			}
		)
		user.flags.no_welcome_mail = True
		user.insert(ignore_permissions=True)
		return user.name

	def _make_event(self, course, title=EVENT_TITLE):
		event = frappe.get_doc(
			{
				"doctype": "LMS Event",
				"title": title,
				"start_date": today(),
				"end_date": today(),
				"start_time": "09:00:00",
				"end_time": "11:00:00",
				"timezone": "America/New_York",
				"description": "Test event for removing registrants.",
				"event_details": "Test event for removing registrants.",
				"instructors": [{"instructor": "Administrator"}],
				"seat_count": 5,
				"published": 0,
			}
		)
		event.insert(ignore_permissions=True)
		return event.name

	def _register(self, event, member):
		name = (
			frappe.get_doc({"doctype": "LMS Event Registration", "event": event, "member": member})
			.insert(ignore_permissions=True)
			.name
		)
		# Mirror LMSEventRegistration.validate_course_enrollment. Built by hand
		# because adding Batch Course rows to an event fails on the dev DB
		# (tabBatch Course.name is bigint there while the doctype uses hash names).
		frappe.get_doc(
			{
				"doctype": "LMS Enrollment",
				"member": member,
				"course": self.course,
				"enrollment_from_event": event,
			}
		).insert(ignore_permissions=True)
		return name

	def _cleanup(self):
		for email in EMAILS:
			for doctype in ("LMS Event Registration", "LMS Enrollment", "LMS Payment"):
				for name in frappe.get_all(doctype, {"member": email}, pluck="name"):
					frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
		for name in frappe.get_all("LMS Event", {"title": ["like", f"{EVENT_TITLE}%"]}, pluck="name"):
			frappe.db.delete("Comment", {"reference_doctype": "LMS Event", "reference_name": name})
			frappe.delete_doc("LMS Event", name, force=True, ignore_permissions=True)
		for email in EMAILS:
			if frappe.db.exists("User", email):
				frappe.delete_doc("User", email, force=True, ignore_permissions=True)

	def _enrollment(self, member):
		return frappe.db.get_value(
			"LMS Enrollment",
			{"member": member, "course": self.course, "enrollment_from_event": self.event},
		)

	# tests

	def test_admin_removes_registration_and_frees_seat(self):
		from lms.lms.ceu_event_admin import remove_event_registrations

		self.assertTrue(self._enrollment(self.users[0]))
		res = remove_event_registrations(self.event, [self.regs[0]])

		self.assertFalse(frappe.db.exists("LMS Event Registration", self.regs[0]))
		self.assertTrue(frappe.db.exists("LMS Event Registration", self.regs[1]))
		self.assertEqual(res["registered"], 1)
		self.assertEqual(res["seats_left"], 4)
		self.assertEqual([r["member"] for r in res["removed"]], [self.users[0]])
		self.assertEqual(res["paid"], [])
		# untouched event-created enrollment goes with the registration
		self.assertFalse(self._enrollment(self.users[0]))
		# restorable and audited
		self.assertTrue(
			frappe.db.exists(
				"Deleted Document",
				{"deleted_doctype": "LMS Event Registration", "deleted_name": self.regs[0]},
			)
		)
		self.assertTrue(
			frappe.db.exists(
				"Comment",
				{
					"reference_doctype": "LMS Event",
					"reference_name": self.event,
					"content": ["like", f"%{self.users[0]}%"],
				},
			)
		)

	def test_accepts_json_list_and_removes_several(self):
		from lms.lms.ceu_event_admin import remove_event_registrations

		res = remove_event_registrations(self.event, frappe.as_json(self.regs))
		self.assertEqual(len(res["removed"]), 2)
		self.assertEqual(res["registered"], 0)
		self.assertEqual(res["seats_left"], 5)

	def test_enrollment_with_progress_is_kept(self):
		from lms.lms.ceu_event_admin import remove_event_registrations

		enrollment = self._enrollment(self.users[1])
		frappe.db.set_value("LMS Enrollment", enrollment, "progress", 40)

		res = remove_event_registrations(self.event, [self.regs[1]])

		self.assertFalse(frappe.db.exists("LMS Event Registration", self.regs[1]))
		self.assertTrue(frappe.db.exists("LMS Enrollment", enrollment))
		self.assertEqual(res["kept_courses"][0]["courses"], [self.course])

	def test_paid_registration_is_reported_not_refunded(self):
		from lms.lms.ceu_event_admin import remove_event_registrations

		payment = frappe.get_doc(
			{
				"doctype": "LMS Payment",
				"member": self.users[0],
				"billing_name": "Garrett Test",
				"amount": 225,
				"currency": "USD",
				"payment_for_document_type": "LMS Event",
				"payment_for_document": self.event,
				"payment_received": 1,
			}
		).insert(ignore_permissions=True)
		frappe.db.set_value("LMS Event Registration", self.regs[0], "payment", payment.name)

		res = remove_event_registrations(self.event, [self.regs[0]])

		self.assertEqual(res["paid"][0]["amount"], 225)
		self.assertEqual(res["paid"][0]["payment"], payment.name)
		self.assertTrue(frappe.db.exists("LMS Payment", payment.name))

	def test_registration_from_another_event_is_rejected(self):
		from lms.lms.ceu_event_admin import remove_event_registrations

		with self.assertRaises(frappe.ValidationError):
			remove_event_registrations(self.event, [self.regs[0], self.other_reg])
		# nothing partially removed
		self.assertTrue(frappe.db.exists("LMS Event Registration", self.regs[0]))
		self.assertTrue(frappe.db.exists("LMS Event Registration", self.other_reg))

	def test_student_cannot_remove(self):
		from lms.lms.ceu_event_admin import remove_event_registrations

		frappe.set_user(self.users[2])
		with self.assertRaises(frappe.PermissionError):
			remove_event_registrations(self.event, [self.regs[0]])
		frappe.set_user("Administrator")
		self.assertTrue(frappe.db.exists("LMS Event Registration", self.regs[0]))

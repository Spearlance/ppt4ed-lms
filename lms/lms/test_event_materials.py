"""Event materials: private handouts shown in-page to registered attendees.

Covers the access gate (registrants + admins only), the admin add / rename /
reorder / delete endpoints, inline vs attachment serving, and file cleanup.
"""

from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase
from frappe.utils import add_days, today

from lms.lms.event_materials import (
	add_event_material,
	delete_event_material,
	delete_materials_for_event,
	get_event_materials,
	rename_event_material,
	reorder_event_materials,
	view_event_material,
)
from lms.lms.utils import get_event_details

REG_MODULE = "lms.lms.doctype.lms_event_registration.lms_event_registration"
TITLE_PREFIX = "Garrett Test Event Materials"
ATTENDEE = "garrett.test.materials1@example.com"
OUTSIDER = "garrett.test.materials2@example.com"
PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


class TestEventMaterials(UnitTestCase):
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
		self.attendee = self._make_user(ATTENDEE, 1)
		self.outsider = self._make_user(OUTSIDER, 2)
		self.event = self._make_event("A")
		frappe.get_doc(
			{"doctype": "LMS Event Registration", "event": self.event, "member": self.attendee}
		).insert(ignore_permissions=True)

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
				"last_name": f"Materials {n}",
				"send_welcome_email": 0,
			}
		)
		user.flags.no_welcome_mail = True
		user.insert(ignore_permissions=True)
		user.add_roles("LMS Student")
		return user.name

	def _make_event(self, suffix):
		day = add_days(today(), -1)
		event = frappe.get_doc(
			{
				"doctype": "LMS Event",
				"title": f"{TITLE_PREFIX} {suffix}",
				"start_date": day,
				"end_date": day,
				"start_time": "09:00:00",
				"end_time": "11:00:00",
				"timezone": "America/New_York",
				"description": "Event materials test event.",
				"event_details": "Event materials test event.",
				"instructors": [{"instructor": "Administrator"}],
				"published": 1,
			}
		)
		event.insert(ignore_permissions=True)
		return event.name

	def _upload(self, file_name="handout.pdf", content=PDF_BYTES, is_private=1):
		file_doc = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": f"garrett-test-materials-{frappe.generate_hash(length=8)}-{file_name}",
				"content": content,
				"is_private": is_private,
			}
		)
		file_doc.insert(ignore_permissions=True)
		return file_doc.name

	def _add(self, title="Course slides", **upload_kwargs):
		return add_event_material(event=self.event, title=title, file=self._upload(**upload_kwargs))

	def _cleanup(self):
		for event in frappe.get_all("LMS Event", {"title": ["like", f"{TITLE_PREFIX}%"]}, pluck="name"):
			delete_materials_for_event(event)
			frappe.db.delete("LMS Event Registration", {"event": event})
			frappe.delete_doc("LMS Event", event, ignore_permissions=True, force=True)
		for file_name in frappe.get_all(
			"File", {"file_name": ["like", "garrett-test-materials-%"]}, pluck="name"
		):
			frappe.delete_doc("File", file_name, ignore_permissions=True, force=True)
		for email in (ATTENDEE, OUTSIDER):
			if frappe.db.exists("User", email):
				frappe.delete_doc("User", email, ignore_permissions=True, force=True)

	# ------------------------------------------------------------------ admin

	def test_add_attaches_private_file_and_orders_last(self):
		first = self._add("Slides")
		second = self._add("Assessment form")

		self.assertEqual(first["file_type"], "pdf")
		rows = get_event_materials(self.event)
		self.assertEqual([r["name"] for r in rows], [first["name"], second["name"]])
		# The raw private URL is never handed to the browser.
		self.assertNotIn("file", rows[0])

		attached = frappe.get_all(
			"File",
			{"attached_to_doctype": "LMS Event Material", "attached_to_name": first["name"]},
			["is_private"],
		)
		self.assertEqual(len(attached), 1)
		self.assertEqual(attached[0].is_private, 1)

	def test_add_rejects_unsupported_public_and_foreign_files(self):
		with self.assertRaises(frappe.ValidationError):
			self._add(file_name="notes.txt", content=b"hello")
		with self.assertRaises(frappe.ValidationError):
			self._add(is_private=0)
		with self.assertRaises(frappe.ValidationError):
			add_event_material(event=self.event, title="   ", file=self._upload())

		# A file that is already a material cannot be re-homed.
		material = self._add()
		used_file = frappe.db.get_value(
			"File", {"attached_to_name": material["name"], "attached_to_doctype": "LMS Event Material"}
		)
		with self.assertRaises(frappe.ValidationError):
			add_event_material(event=self.event, title="Again", file=used_file)

	def test_rename_and_reorder(self):
		a = self._add("A")
		b = self._add("B")
		c = self._add("C")

		rename_event_material(name=b["name"], title="  Bravo ")
		rows = reorder_event_materials(event=self.event, names=[c["name"], a["name"], b["name"]])
		self.assertEqual([r["title"] for r in rows], ["C", "A", "Bravo"])

	def test_delete_removes_the_file(self):
		material = self._add()
		file_name = frappe.db.get_value(
			"File", {"attached_to_name": material["name"], "attached_to_doctype": "LMS Event Material"}
		)
		delete_event_material(name=material["name"])
		self.assertFalse(frappe.db.exists("LMS Event Material", material["name"]))
		self.assertFalse(frappe.db.exists("File", file_name))

	def test_students_cannot_manage(self):
		material = self._add()
		file_name = self._upload()
		frappe.set_user(self.attendee)
		with self.assertRaises(frappe.PermissionError):
			add_event_material(event=self.event, title="Nope", file=file_name)
		with self.assertRaises(frappe.PermissionError):
			rename_event_material(name=material["name"], title="Nope")
		with self.assertRaises(frappe.PermissionError):
			delete_event_material(name=material["name"])
		with self.assertRaises(frappe.PermissionError):
			reorder_event_materials(event=self.event, names=[material["name"]])

	# ------------------------------------------------------------------ viewing

	def test_registered_attendee_views_inline(self):
		material = self._add("Turtle Brace Slideshow 11.7.26")
		frappe.set_user(self.attendee)

		self.assertEqual(len(get_event_materials(self.event)), 1)
		response = view_event_material(name=material["name"])
		self.assertEqual(response.mimetype, "application/pdf")
		self.assertEqual(response.get_data(), PDF_BYTES)
		self.assertTrue(response.headers["Content-Disposition"].startswith("inline"))
		self.assertIn("Turtle-Brace-Slideshow-11.7.26.pdf", response.headers["Content-Disposition"])

		download = view_event_material(name=material["name"], download="1")
		self.assertTrue(download.headers["Content-Disposition"].startswith("attachment"))

	def test_unregistered_and_guest_are_blocked(self):
		material = self._add()
		for user in (self.outsider, "Guest"):
			frappe.set_user(user)
			with self.assertRaises(frappe.PermissionError):
				get_event_materials(self.event)
			with self.assertRaises(frappe.PermissionError):
				view_event_material(name=material["name"])

	def test_event_details_count_is_hidden_from_non_attendees(self):
		self._add()
		self._add("Second")

		frappe.set_user(self.attendee)
		self.assertEqual(get_event_details(self.event).materials_count, 2)

		frappe.set_user(self.outsider)
		self.assertEqual(get_event_details(self.event).materials_count, 0)

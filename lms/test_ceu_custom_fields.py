import frappe
from frappe.tests import UnitTestCase


class TestCEUCustomFields(UnitTestCase):
    def test_course_has_ceu_hours_field(self):
        meta = frappe.get_meta("LMS Course")
        self.assertTrue(meta.has_field("ceu_hours"))

    def test_course_has_disciplines_field(self):
        meta = frappe.get_meta("LMS Course")
        self.assertTrue(meta.has_field("disciplines"))

    def test_enrollment_has_credit_source_field(self):
        meta = frappe.get_meta("LMS Enrollment")
        self.assertTrue(meta.has_field("credit_source"))

    def test_enrollment_has_ceu_hours_awarded_field(self):
        meta = frappe.get_meta("LMS Enrollment")
        self.assertTrue(meta.has_field("ceu_hours_awarded"))

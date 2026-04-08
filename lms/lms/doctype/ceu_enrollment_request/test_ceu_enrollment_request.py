import frappe
from frappe.tests import UnitTestCase


class TestCEUEnrollmentRequest(UnitTestCase):
    def test_create_enrollment_request(self):
        doc = frappe.get_doc({
            "doctype": "CEU Enrollment Request",
            "user": "Administrator",
            "status": "Pending"
        })
        doc.insert(ignore_permissions=True)
        self.assertEqual(doc.status, "Pending")

    def test_approve_enrollment_request(self):
        doc = frappe.get_doc({
            "doctype": "CEU Enrollment Request",
            "user": "Administrator",
            "status": "Pending"
        })
        doc.insert(ignore_permissions=True)
        doc.status = "Approved"
        doc.reviewed_by = "Administrator"
        doc.save(ignore_permissions=True)
        self.assertEqual(doc.status, "Approved")

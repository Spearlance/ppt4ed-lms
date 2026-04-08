import frappe
from frappe.tests import UnitTestCase


class TestCEUDiscipline(UnitTestCase):
    def test_create_discipline(self):
        doc = frappe.get_doc({
            "doctype": "CEU Discipline",
            "discipline_name": "Occupational Therapy"
        })
        doc.insert(ignore_permissions=True)
        self.assertEqual(doc.discipline_name, "Occupational Therapy")
        self.assertTrue(frappe.db.exists("CEU Discipline", "Occupational Therapy"))

    def test_duplicate_discipline_rejected(self):
        frappe.get_doc({
            "doctype": "CEU Discipline",
            "discipline_name": "Physical Therapy"
        }).insert(ignore_permissions=True)

        with self.assertRaises(frappe.DuplicateEntryError):
            frappe.get_doc({
                "doctype": "CEU Discipline",
                "discipline_name": "Physical Therapy"
            }).insert(ignore_permissions=True)

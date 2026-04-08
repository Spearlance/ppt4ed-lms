import frappe
from frappe import _
from frappe.model.document import Document


class CompanyAccount(Document):
    def validate(self):
        self.validate_admins()

    def validate_admins(self):
        admin_users = [a.user for a in self.admins]
        if len(admin_users) != len(set(admin_users)):
            frappe.throw(_("Duplicate admin entries are not allowed"))

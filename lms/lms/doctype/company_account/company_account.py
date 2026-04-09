import frappe
from frappe import _
from frappe.model.document import Document


class CompanyAccount(Document):
    def validate(self):
        self.validate_admins()
        self.validate_max_seats()

    def validate_admins(self):
        admin_users = [a.user for a in self.admins]
        if len(admin_users) != len(set(admin_users)):
            frappe.throw(_("Duplicate admin entries are not allowed"))

    def validate_max_seats(self):
        if self.max_seats and self.max_seats > 0:
            active_members = [m for m in self.members if m.status == "Active"]
            if len(active_members) > self.max_seats:
                frappe.throw(
                    _("Cannot exceed {0} seats. Currently have {1} active members.").format(
                        self.max_seats, len(active_members)
                    ),
                    frappe.ValidationError
                )

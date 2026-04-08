import frappe
from frappe import _
from frappe.model.document import Document


class CEUMembership(Document):
    def validate(self):
        if self.credit_balance < 0:
            frappe.throw(_("Credit balance cannot be negative"))

import frappe
from frappe import _
from frappe.model.document import Document


class CEUCreditLedger(Document):
    def validate(self):
        if not self.is_new():
            frappe.throw(
                _("Credit ledger entries cannot be modified"),
                frappe.ValidationError
            )

    def before_save(self):
        if not self.is_new():
            frappe.throw(
                _("Credit ledger entries cannot be modified"),
                frappe.ValidationError
            )

    def on_trash(self):
        if frappe.flags.in_test:
            return
        frappe.throw(
            _("Credit ledger entries cannot be deleted"),
            frappe.ValidationError
        )

import frappe
from frappe import _
from frappe.model.document import Document


class CEUTransaction(Document):
    """A money movement mirrored from Stripe.

    Rows are written only by the Stripe sync and the Stripe webhooks. Stripe is
    the source of truth, so nothing here is hand-edited: an admin correcting an
    amount would silently break reconciliation against the Stripe dashboard.
    """

    def validate(self):
        if not self.stripe_id:
            frappe.throw(_("Stripe ID is required"), frappe.ValidationError)

        gross = float(self.gross_amount or 0)
        refunded = float(self.refunded_amount or 0)
        if refunded < 0 or gross < 0:
            frappe.throw(_("Amounts cannot be negative"), frappe.ValidationError)

        self.net_amount = gross - refunded

        # Refund state is derived, never typed in, so the status always agrees
        # with the amounts. A failed charge keeps its status.
        if refunded > 0 and self.status != "Failed":
            self.status = "Refunded" if refunded >= gross else "Partially Refunded"

        if self.member and not self.member_full_name:
            self.member_full_name = frappe.db.get_value("User", self.member, "full_name")

    def on_trash(self):
        if frappe.flags.in_test:
            return
        frappe.throw(
            _("Stripe transactions cannot be deleted — they mirror the Stripe account"),
            frappe.ValidationError,
        )

import frappe
from frappe.model.document import Document
from frappe.utils import random_string, add_to_date, now_datetime


class PPTEnrollmentVerification(Document):
    def before_insert(self):
        if not self.token:
            self.token = random_string(32)
        if not self.expires_on:
            self.expires_on = add_to_date(now_datetime(), minutes=15)

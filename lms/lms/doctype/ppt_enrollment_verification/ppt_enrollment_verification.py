import frappe
from frappe.model.document import Document
from frappe.utils import add_to_date, now_datetime, random_string


class PPTEnrollmentVerification(Document):
	"""Holds a pending public signup for a PPT-internal email address until the
	person proves they own the inbox. Created by `start_ppt_signup`, consumed
	by `verify_ppt_signup`. Doctype name is legacy — kept to avoid a doctype
	rename migration on a dormant table."""

	def before_insert(self):
		if not self.token:
			# 48 chars from random_string (lowercase alphanumeric) — ~248 bits.
			# Well over the standard 128-bit unguessable-token threshold.
			self.token = random_string(48)
		if not self.expires_on:
			self.expires_on = add_to_date(now_datetime(), minutes=15)

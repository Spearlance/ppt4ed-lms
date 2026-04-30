# Copyright (c) 2021, FOSS United and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_url_to_list, validate_email_address, validate_url


class LMSSettings(Document):
	def validate(self):
		self.validate_google_settings()
		self.validate_signup()
		self.validate_contact_us_details()

	def validate_google_settings(self):
		if self.send_calendar_invite_for_evaluations:
			google_settings = frappe.get_single("Google Settings")

			if not google_settings.enable:
				frappe.throw(
					_("Enable Google API in Google Settings to send calendar invites for evaluations.")
				)

			if not google_settings.client_id or not google_settings.client_secret:
				frappe.throw(
					_(
						"Enter Client Id and Client Secret in Google Settings to send calendar invites for evaluations."
					)
				)

			calendars = frappe.db.count("Google Calendar")
			if not calendars:
				frappe.throw(
					_(
						"Please add <a href='{0}'>{1}</a> for <a href='{2}'>{3}</a> to send calendar invites for evaluations."
					).format(
						get_url_to_list("Google Calendar"),
						frappe.bold("Google Calendar"),
						get_url_to_list("Course Evaluator"),
						frappe.bold("Course Evaluator"),
					)
				)

	def validate_signup(self):
		if self.has_value_changed("disable_signup"):
			frappe.db.set_single_value("Website Settings", "disable_signup", self.disable_signup)

	def validate_contact_us_details(self):
		if self.contact_us_email and not validate_email_address(self.contact_us_email):
			frappe.throw(_("Please enter a valid Contact Us Email."))
		if self.contact_us_url and not validate_url(self.contact_us_url, True, ["http", "https"]):
			frappe.throw(_("Please enter a valid Contact Us URL."))

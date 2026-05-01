import frappe
from frappe import _
from frappe.utils import cint, get_datetime, getdate
from frappe.website.website_generator import WebsiteGenerator

from lms.lms.utils import generate_slug


class CommunityEvent(WebsiteGenerator):
	website = frappe._dict(
		# Path is relative to the app root. Frappe's DocumentPage renderer
		# uses this to resolve the Jinja template; without it, template_path
		# is None and rendering crashes inside Jinja's loader.
		template="templates/generators/community_event.html",
		condition_field="published",
		page_title_field="title",
	)

	def autoname(self):
		if not self.name:
			self.name = generate_slug(self.title, "Community Event")

	def make_route(self):
		# Public URL is /community-events/<slug>. WebsiteGenerator only calls this
		# when self.route is unset, so admins can edit the route field manually if
		# they need a custom path.
		return f"community-events/{self.name}"

	def validate(self):
		# WebsiteGenerator's auto-route only fires when the doc is already
		# website-published. Events are typically created as Drafts and
		# flipped to Published later, so the auto-fill never runs and the
		# public URL stays unresolvable. Force-fill on every save so the
		# route is stable from creation onward.
		if not self.route:
			self.route = self.make_route()
		self.validate_dates()
		self.validate_capacity()
		self.validate_donation_amount()

	def validate_dates(self):
		if not self.end_date:
			self.end_date = self.start_date
		if getdate(self.end_date) < getdate(self.start_date):
			frappe.throw(_("End date cannot be before the start date."))

		if self.start_time and self.end_time and self.start_date == self.end_date:
			start = get_datetime(f"{self.start_date} {self.start_time}")
			end = get_datetime(f"{self.end_date} {self.end_time}")
			if end <= start:
				frappe.throw(_("End time must be after start time on a single-day event."))

	def validate_capacity(self):
		if cint(self.max_attendees) < 0:
			frappe.throw(_("Max attendees cannot be negative."))

	def validate_donation_amount(self):
		if self.additional_attendee_amount and float(self.additional_attendee_amount) < 0:
			frappe.throw(_("Donation amount cannot be negative."))

	def get_context(self, context):
		# Rendered into community_event.html. Keep this minimal — the template
		# is public and shouldn't leak admin-only fields.
		context.no_cache = 1
		context.event = self
		context.title = self.title
		context.confirmed_attendees = get_confirmed_attendee_count(self.name)
		context.seats_remaining = (
			max(cint(self.max_attendees) - context.confirmed_attendees, 0)
			if cint(self.max_attendees)
			else None
		)
		context.is_full = (
			cint(self.max_attendees) > 0
			and context.confirmed_attendees >= cint(self.max_attendees)
		)


def get_confirmed_attendee_count(event_name: str) -> int:
	"""Sum attendee_count over registrations that are Free or Confirmed.

	Pending registrations are excluded so a stalled Stripe checkout doesn't
	hold seats forever. Stripe sessions auto-expire after 24h.
	"""
	rows = frappe.get_all(
		"Community Event Registration",
		filters={
			"parent_event": event_name,
			"payment_status": ["in", ["Free", "Confirmed"]],
		},
		fields=["attendee_count"],
	)
	return sum(cint(r.attendee_count) for r in rows)


def has_permission(doc, ptype="read", user=None):
	"""Public read access for published events. Otherwise admin-only.

	The public RSVP page is served via WebsiteGenerator and bypasses this
	check for guests; this is the doctype-level guard for direct API access.
	"""
	user = user or frappe.session.user
	if ptype in ("read", "select", "print"):
		if doc.published:
			return True
	roles = frappe.get_roles(user)
	if any(r in roles for r in ("System Manager", "Moderator", "Global Admin")):
		return True
	return False

"""Normalize button colors in seeded Email Template bodies to the PPT4ed brand
dark-blue (#0b6685). Previously seeded with stock #171717 (black) or #2563eb
(blue). The shared brand wrapper added alongside this patch already supplies
the chrome; matching the inner CTA button keeps the result visually cohesive.

Narrow + idempotent: only swaps the exact hex strings inside `background:` /
`background-color:` declarations. Admin-edited copy (which would not include
these specific hex values) is untouched.
"""

import re

import frappe


# Templates seeded by lms/patches/v2_0/seed_*template*.py
TEMPLATE_NAMES = (
	"Mention Notification",
	"Event Starting Tomorrow",
	"Event Starting in One Hour",
	"Live Class Reminder",
	"New Event Published",
	"New Course Published",
	"Course Now Available",
	"Company Member Invite",
	"Company Admin Invite",
	"LMS Member Welcome",
	"Community Event Confirmation",
	"Event Announcement",
	"Event Starting in 15 Minutes",
	"Removed from Company",
)

BRAND_BUTTON_HEX = "#0b6685"
OLD_HEXES = ("#171717", "#2563eb")
PATTERN = re.compile(
	r"(background(?:-color)?\s*:\s*)(" + "|".join(re.escape(h) for h in OLD_HEXES) + r")",
	re.IGNORECASE,
)


def execute():
	for name in TEMPLATE_NAMES:
		if not frappe.db.exists("Email Template", name):
			continue
		body = frappe.db.get_value("Email Template", name, "response_html") or ""
		new_body = PATTERN.sub(lambda m: m.group(1) + BRAND_BUTTON_HEX, body)
		if new_body != body:
			frappe.db.set_value("Email Template", name, "response_html", new_body)

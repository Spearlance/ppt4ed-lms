"""Traffic-source attribution for signups and enrollments.

The browser half lives in `templates/includes/traffic_source.html`: it stores
where a visitor came from (UTM tags, an ad click ID, or the referring site) in
the `lms_traffic_src` cookie. This module is the server half. It reads that
cookie when an account or enrollment is created so Admin Reports > Sources can
answer "which channel drove this signup?".

Everything here fails open. Attribution is reporting data and must never block
a signup, an enrollment or a Stripe webhook.
"""

import json
from urllib.parse import unquote

import frappe

COOKIE_NAME = "lms_traffic_src"
FIELDS = ("source", "medium", "campaign", "referrer")
MAX_LENGTH = 140

# The browser script only writes the cookie when it has something to record, so
# a browser without one arrived with no UTM tags and no referring site.
DIRECT = {"source": "direct", "medium": "none", "campaign": "", "referrer": ""}


def _clean(value):
	"""Normalise one cookie value. The cookie is visitor-controlled and ends up
	in an admin CSV export, so drop the characters a spreadsheet treats as the
	start of a formula."""
	if not isinstance(value, str):
		return ""
	return " ".join(value.split()).lower().lstrip("=+-@")[:MAX_LENGTH]


def parse_traffic_source(raw):
	"""Parse the cookie value into {source, medium, campaign, referrer}.

	Returns None if it is not ours or names no source.
	"""
	if not raw:
		return None

	# Werkzeug has percent-decoded cookie values in some versions and not in
	# others, so accept either form.
	for candidate in (raw, unquote(raw)):
		try:
			data = json.loads(candidate)
		except ValueError:
			continue
		if isinstance(data, dict):
			traffic = {key: _clean(data.get(key)) for key in FIELDS}
			return traffic if traffic["source"] else None

	return None


def get_request_traffic_source():
	"""Source of the browser making the current request.

	Returns None when there is no browser to attribute: no request at all
	(scheduler, console), or a request carrying no cookies (the Stripe webhook,
	which impersonates the buyer for paid events, or an API-key client). A real
	browser always sends at least Frappe's session cookie. Returns DIRECT when
	a browser arrived without our cookie. Never raises.
	"""
	try:
		request = getattr(frappe.local, "request", None)
		if not request or not request.cookies:
			return None
		return parse_traffic_source(request.cookies.get(COOKIE_NAME)) or dict(DIRECT)
	except Exception:
		return None


def traffic_fields(traffic, prefix="traffic_"):
	"""Map a parsed source onto doc fieldnames, e.g. `traffic_source`."""
	return {f"{prefix}{key}": traffic.get(key) or "" for key in FIELDS}


def save_signup_traffic_source(user):
	"""Stamp the current browser's source onto a freshly created User.

	Call only while the visitor's own request is being served. Never raises.
	"""
	try:
		traffic = get_request_traffic_source()
		if traffic:
			frappe.db.set_value(
				"User",
				user,
				traffic_fields(traffic, prefix="signup_traffic_"),
				update_modified=False,
			)
	except Exception:
		frappe.log_error(title="Signup traffic source not saved")


def checkout_traffic_metadata():
	"""Stripe Checkout metadata that carries the current browser's source to
	the webhook, which has no browser of its own to read a cookie from."""
	traffic = get_request_traffic_source()
	if not traffic:
		return {}
	return {name: value for name, value in traffic_fields(traffic).items() if value}


def traffic_fields_from_metadata(metadata):
	"""Inverse of `checkout_traffic_metadata`, for the Stripe webhook."""
	metadata = metadata or {}
	fields = {f"traffic_{key}": _clean(metadata.get(f"traffic_{key}")) for key in FIELDS}
	return fields if fields["traffic_source"] else {}

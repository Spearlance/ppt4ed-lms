import json
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import quote

import frappe
from frappe.tests import UnitTestCase

from lms.lms.traffic_source import (
	COOKIE_NAME,
	DIRECT,
	checkout_traffic_metadata,
	get_request_traffic_source,
	parse_traffic_source,
	traffic_fields,
	traffic_fields_from_metadata,
)


def _cookie(**values):
	return quote(json.dumps(values))


def _request(cookies):
	return patch.object(frappe.local, "request", SimpleNamespace(cookies=cookies), create=True)


class TestTrafficSource(UnitTestCase):
	def test_parses_percent_encoded_and_plain_cookie(self):
		expected = {"source": "newsletter", "medium": "email", "campaign": "fall-2026", "referrer": ""}
		encoded = _cookie(source="Newsletter", medium="email", campaign="fall-2026")

		self.assertEqual(parse_traffic_source(encoded), expected)
		self.assertEqual(
			parse_traffic_source('{"source": "newsletter", "medium": "email", "campaign": "fall-2026"}'),
			expected,
		)

	def test_rejects_garbage_and_sourceless_cookies(self):
		self.assertIsNone(parse_traffic_source(""))
		self.assertIsNone(parse_traffic_source("not json"))
		self.assertIsNone(parse_traffic_source(quote("[1, 2]")))
		self.assertIsNone(parse_traffic_source(_cookie(medium="email")))

	def test_cleans_values_bound_for_a_spreadsheet(self):
		parsed = parse_traffic_source(_cookie(source="=cmd|' /c calc'!a1", campaign="x" * 500, medium=7))

		self.assertFalse(parsed["source"].startswith("="))
		self.assertEqual(len(parsed["campaign"]), 140)
		self.assertEqual(parsed["medium"], "")

	def test_browser_without_our_cookie_is_direct(self):
		with _request({"sid": "abc"}):
			self.assertEqual(get_request_traffic_source(), DIRECT)

	def test_request_without_any_cookie_is_not_attributed(self):
		"""The Stripe webhook is a request, but it is not the buyer's browser."""
		with _request({}):
			self.assertIsNone(get_request_traffic_source())
			self.assertEqual(checkout_traffic_metadata(), {})

	def test_checkout_metadata_round_trips_to_enrollment_fields(self):
		cookies = {"sid": "abc", COOKIE_NAME: _cookie(source="google", medium="cpc", referrer="google.com")}
		with _request(cookies):
			metadata = checkout_traffic_metadata()

		# Blank values are left out rather than sent to Stripe as empty strings.
		self.assertEqual(
			metadata,
			{"traffic_source": "google", "traffic_medium": "cpc", "traffic_referrer": "google.com"},
		)
		self.assertEqual(
			traffic_fields_from_metadata({"type": "one_off", **metadata}),
			traffic_fields({"source": "google", "medium": "cpc", "referrer": "google.com"}),
		)

	def test_metadata_without_a_source_yields_no_fields(self):
		self.assertEqual(traffic_fields_from_metadata({"type": "one_off", "course": "c"}), {})
		self.assertEqual(traffic_fields_from_metadata(None), {})

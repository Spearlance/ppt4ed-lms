from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from lms.lms import signup_webhook
from lms.lms.signup_webhook import CONFIG_KEY, build_payload, deliver, queue_signup_webhook

HOOK = "https://hooks.example.test/catch"

MEMBER = {
	"email": "pat@example.com",
	"full_name": "Pat Lee",
	"first_name": "Pat",
	"last_name": "Lee",
	"notification_audience": "Educators",
}

RESOURCE = {
	"title": "Sensory Play at Home",
	"course_type": "Resource",
	"resource_type": "Download",
	"audience": "Parents / Caregivers",
	"paid_course": 0,
}

COURSE = {
	"title": "Classroom Regulation",
	"course_type": "Course",
	"resource_type": None,
	"audience": "Educators",
	"paid_course": 1,
}


def _site(rows=None, url=HOOK):
	"""Stand in for the site: config, the rows `get_value` can see, and the
	site URL. Keeps these tests off the database."""
	rows = rows or {}

	def get_value(doctype, name, fields=None, as_dict=False):
		row = rows.get((doctype, name))
		return frappe._dict(row) if row else None

	patches = (
		patch.object(frappe, "conf", frappe._dict({CONFIG_KEY: url} if url else {})),
		patch.object(frappe, "db", SimpleNamespace(get_value=get_value)),
		patch.object(signup_webhook, "get_url", lambda path="": f"https://lms.test{path}"),
	)

	class Site:
		def __enter__(self):
			for item in patches:
				item.start()

		def __exit__(self, *exc):
			for item in reversed(patches):
				item.stop()

	return Site()


class TestSignupWebhook(UnitTestCase):
	def test_nothing_is_queued_without_a_configured_url(self):
		with _site(url=None), patch.object(frappe, "enqueue") as enqueue:
			queue_signup_webhook("LMS Enrollment", "ENR-1")

		enqueue.assert_not_called()

	def test_delivery_is_queued_for_after_the_commit(self):
		with _site(), patch.object(frappe, "enqueue") as enqueue:
			queue_signup_webhook("LMS Enrollment", "ENR-1")

		enqueue.assert_called_once_with(
			"lms.lms.signup_webhook.deliver",
			queue="short",
			enqueue_after_commit=True,
			source_doctype="LMS Enrollment",
			source_name="ENR-1",
		)

	def test_queueing_never_raises(self):
		with (
			_site(),
			patch.object(frappe, "enqueue", side_effect=RuntimeError("redis down")),
			patch.object(frappe, "log_error") as log_error,
		):
			queue_signup_webhook("LMS Enrollment", "ENR-1")

		log_error.assert_called_once()

	def test_resource_signup_carries_the_content_audience(self):
		rows = {
			("LMS Enrollment", "ENR-1"): {
				"creation": "2026-10-02 09:30:00",
				"member": "pat@example.com",
				"course": "sensory-play",
				"traffic_source": "newsletter",
				"traffic_medium": "email",
				"traffic_campaign": "fall-2026",
				"traffic_referrer": "",
			},
			("User", "pat@example.com"): MEMBER,
			("LMS Course", "sensory-play"): RESOURCE,
		}
		with _site(rows):
			payload = build_payload("LMS Enrollment", "ENR-1")

		self.assertEqual(payload["event"], "resource_signup")
		self.assertEqual(payload["item_type"], "Resource")
		self.assertEqual(payload["audience"], "Parents / Caregivers")
		self.assertEqual(payload["resource_type"], "Download")
		self.assertEqual(payload["item_url"], "https://lms.test/lms/resources/sensory-play")
		self.assertEqual(payload["email"], "pat@example.com")
		# The member's own preference is reported separately from the content's.
		self.assertEqual(payload["user_audience"], "Educators")
		self.assertEqual(payload["traffic_source"], "newsletter")
		self.assertIs(payload["paid"], False)

	def test_course_enrollment_is_told_apart_from_a_resource(self):
		rows = {
			("LMS Enrollment", "ENR-2"): {
				"creation": "2026-10-02 09:30:00",
				"member": "pat@example.com",
				"course": "classroom-regulation",
			},
			("User", "pat@example.com"): MEMBER,
			("LMS Course", "classroom-regulation"): COURSE,
		}
		with _site(rows):
			payload = build_payload("LMS Enrollment", "ENR-2")

		self.assertEqual(payload["event"], "course_enrollment")
		self.assertEqual(payload["item_type"], "Course")
		self.assertEqual(payload["audience"], "Educators")
		self.assertEqual(payload["item_url"], "https://lms.test/lms/courses/classroom-regulation")
		self.assertEqual(payload["traffic_source"], "")
		self.assertIs(payload["paid"], True)

	def test_account_signup_names_the_page_it_happened_on(self):
		rows = {
			("User", "pat@example.com"): {
				**MEMBER,
				"creation": "2026-10-02 09:29:00",
				"signup_source": "sensory-play",
				"signup_source_type": "Resource",
				"signup_traffic_source": "google",
				"signup_traffic_medium": "cpc",
			},
			("LMS Course", "sensory-play"): RESOURCE,
		}
		with _site(rows):
			payload = build_payload("User", "pat@example.com")

		self.assertEqual(payload["event"], "account_signup")
		self.assertEqual(payload["item_type"], "Resource")
		self.assertEqual(payload["audience"], "Parents / Caregivers")
		self.assertEqual(payload["traffic_source"], "google")
		self.assertEqual(payload["traffic_medium"], "cpc")

	def test_direct_account_signup_has_no_item(self):
		rows = {
			("User", "pat@example.com"): {
				**MEMBER,
				"creation": "2026-10-02 09:29:00",
				"signup_source": None,
				"signup_source_type": "Direct",
			},
		}
		with _site(rows):
			payload = build_payload("User", "pat@example.com")

		self.assertEqual(payload["event"], "account_signup")
		self.assertEqual(payload["item_type"], "")
		self.assertEqual(payload["audience"], "")

	def test_event_registration_payload(self):
		rows = {
			("LMS Event Registration", "REG-1"): {
				"creation": "2026-10-02 10:00:00",
				"member": "pat@example.com",
				"event": "fall-webinar",
			},
			("User", "pat@example.com"): MEMBER,
			("LMS Event", "fall-webinar"): {
				"title": "Fall Webinar",
				"audience": "Healthcare Professionals",
				"paid_event": 1,
			},
		}
		with _site(rows):
			payload = build_payload("LMS Event Registration", "REG-1")

		self.assertEqual(payload["event"], "event_registration")
		self.assertEqual(payload["item_type"], "Event")
		self.assertEqual(payload["item_title"], "Fall Webinar")
		self.assertEqual(payload["audience"], "Healthcare Professionals")
		self.assertIs(payload["paid"], True)

	def test_community_event_contact_is_the_guardian(self):
		rows = {
			("Community Event Registration", "CER-1"): {
				"creation": "2026-10-02 11:00:00",
				"parent_event": "family-fun-day",
				"guardian_name": "Sam Rivera Jr",
				"guardian_email": "sam@example.com",
				"guardian_phone": "555-0100",
				"donation_total": 0,
			},
			("Community Event", "family-fun-day"): {
				"title": "Family Fun Day",
				"route": "community-events/family-fun-day",
			},
		}
		with _site(rows):
			payload = build_payload("Community Event Registration", "CER-1")

		self.assertEqual(payload["event"], "community_event_registration")
		self.assertEqual(payload["email"], "sam@example.com")
		self.assertEqual(payload["first_name"], "Sam")
		self.assertEqual(payload["last_name"], "Rivera Jr")
		self.assertEqual(payload["phone"], "555-0100")
		self.assertEqual(payload["item_url"], "https://lms.test/community-events/family-fun-day")
		self.assertIs(payload["paid"], False)

	def test_links_are_https_and_time_is_to_the_second(self):
		"""The delivery job has no request, so `get_url` hands back http://."""
		rows = {
			("LMS Enrollment", "ENR-1"): {
				"creation": "2026-10-02 09:30:00.123456",
				"member": "pat@example.com",
				"course": "sensory-play",
			},
			("User", "pat@example.com"): MEMBER,
			("LMS Course", "sensory-play"): RESOURCE,
		}
		with _site(rows), patch.object(signup_webhook, "get_url", lambda path="": f"http://lms.test{path}"):
			payload = build_payload("LMS Enrollment", "ENR-1")

		self.assertEqual(payload["site"], "https://lms.test")
		self.assertEqual(payload["item_url"], "https://lms.test/lms/resources/sensory-play")
		self.assertEqual(payload["occurred_at"], "2026-10-02 09:30:00")

	def test_every_event_sends_the_same_keys(self):
		rows = {
			("LMS Enrollment", "ENR-1"): {"creation": "", "member": "pat@example.com", "course": "sensory-play"},
			("User", "pat@example.com"): {**MEMBER, "creation": ""},
			("LMS Course", "sensory-play"): RESOURCE,
			("Community Event Registration", "CER-1"): {"creation": "", "parent_event": "gone"},
		}
		with _site(rows):
			keys = {
				frozenset(build_payload(doctype, name))
				for doctype, name in (
					("LMS Enrollment", "ENR-1"),
					("User", "pat@example.com"),
					("Community Event Registration", "CER-1"),
				)
			}

		self.assertEqual(len(keys), 1)

	def test_delivery_posts_the_payload(self):
		rows = {
			("LMS Enrollment", "ENR-1"): {"creation": "", "member": "pat@example.com", "course": "sensory-play"},
			("User", "pat@example.com"): MEMBER,
			("LMS Course", "sensory-play"): RESOURCE,
		}
		with _site(rows), patch.object(signup_webhook.requests, "post") as post:
			deliver("LMS Enrollment", "ENR-1")

		post.assert_called_once()
		self.assertEqual(post.call_args.args[0], HOOK)
		self.assertEqual(post.call_args.kwargs["json"]["event"], "resource_signup")
		self.assertEqual(post.call_args.kwargs["timeout"], signup_webhook.TIMEOUT)

	def test_deleted_document_sends_nothing(self):
		with _site(), patch.object(signup_webhook.requests, "post") as post:
			deliver("LMS Enrollment", "ENR-GONE")

		post.assert_not_called()

	def test_failed_delivery_is_logged_not_raised(self):
		rows = {
			("LMS Enrollment", "ENR-1"): {"creation": "", "member": "pat@example.com", "course": "sensory-play"},
			("User", "pat@example.com"): MEMBER,
			("LMS Course", "sensory-play"): RESOURCE,
		}
		with (
			_site(rows),
			patch.object(signup_webhook.requests, "post", side_effect=RuntimeError("timeout")),
			patch.object(frappe, "log_error") as log_error,
		):
			deliver("LMS Enrollment", "ENR-1")

		log_error.assert_called_once()

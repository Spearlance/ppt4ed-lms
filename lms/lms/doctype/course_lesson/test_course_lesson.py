# Copyright (c) 2021, FOSS United and Contributors
# See license.txt

import json
import unittest

import frappe

from lms.lms.doctype.course_lesson.course_lesson import lesson_has_videos


def make_lesson(blocks=None, youtube=None, body=None):
	content = json.dumps({"blocks": blocks}) if blocks is not None else None
	return frappe._dict(youtube=youtube, content=content, body=body)


def upload_block(file_type):
	return {"type": "upload", "data": {"file_url": "/files/f", "file_type": file_type}}


class TestCourseLesson(unittest.TestCase):
	def test_pdf_upload_block_is_not_a_video(self):
		# A PDF renders as an iframe — no player, no watch record — so it must
		# not trip the video gate that locks subsequent lessons.
		self.assertFalse(lesson_has_videos(make_lesson(blocks=[upload_block("PDF")])))

	def test_image_and_audio_upload_blocks_are_not_videos(self):
		for file_type in ("jpg", "png", "image", "mp3", "wav"):
			self.assertFalse(
				lesson_has_videos(make_lesson(blocks=[upload_block(file_type)])),
				f"file_type={file_type} should not count as a video",
			)

	def test_video_upload_blocks_are_videos(self):
		for file_type in ("mp4", "MOV", "webm", "avi", "mkv"):
			self.assertTrue(
				lesson_has_videos(make_lesson(blocks=[upload_block(file_type)])),
				f"file_type={file_type} should count as a video",
			)

	def test_upload_block_without_file_type_is_not_a_video(self):
		self.assertFalse(
			lesson_has_videos(make_lesson(blocks=[{"type": "upload", "data": {}}]))
		)

	def test_youtube_field_is_a_video(self):
		self.assertTrue(lesson_has_videos(make_lesson(youtube="https://youtu.be/x")))

	def test_video_macro_in_body_is_a_video(self):
		self.assertTrue(lesson_has_videos(make_lesson(body="{{ YouTubeVideo('abc') }}")))

	def test_plain_lesson_has_no_videos(self):
		self.assertFalse(
			lesson_has_videos(make_lesson(blocks=[{"type": "markdown", "data": {"text": "hi"}}]))
		)

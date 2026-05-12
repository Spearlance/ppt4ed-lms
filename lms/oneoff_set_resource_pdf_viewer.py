"""
One-off fix: swap the markdown "Download PDF" link in caregiver Free Resources
for Frappe LMS's native inline PDF viewer.

`oneoff_populate_resources.py` created 15 single-lesson Download resources whose
lesson `body` was a Markdown blob ending in `[Download PDF](/files/xxx.pdf)`.
The PDFs are attached as Frappe Files and downloadable, but they only render as
a small inline hyperlink — caregivers expect to see the PDF embedded.

`ResourceOverview.vue` prefers `lesson.content` (EditorJS JSON) over
`lesson.body` (Markdown). The EditorJS `upload` tool renders a `file_type=PDF`
block as a full-width `<iframe>` PDF viewer (see frontend/src/utils/upload.js).

So: for each Resource course with a single Course Lesson and an attached PDF,
write an EditorJS payload with one `upload` block pointing to the existing PDF
file. `body` is left alone as a fallback in case `content` ever gets cleared.

Run with:

    docker exec lms-backend-1 bench --site devlms.ppt4ed.org \
        execute lms.oneoff_set_resource_pdf_viewer.run

Dry-run (rolls back at end):

    docker exec lms-backend-1 bench --site devlms.ppt4ed.org \
        execute lms.oneoff_set_resource_pdf_viewer.run --kwargs '{"dry_run": true}'

Idempotent: if a lesson's `content` already contains an `upload`/PDF block, it
is skipped.
"""

import json
import secrets
import time

import frappe


EDITORJS_VERSION = "2.29.0"


def _build_pdf_content(pdf_file_url: str) -> str:
	"""Build an EditorJS JSON payload with a single `upload` PDF block."""
	payload = {
		"time": int(time.time() * 1000),
		"blocks": [
			{
				"id": secrets.token_urlsafe(7)[:10],
				"type": "upload",
				"data": {
					"file_url": pdf_file_url,
					"file_type": "PDF",
					"quizzes": [],
				},
			}
		],
		"version": EDITORJS_VERSION,
	}
	return json.dumps(payload)


def _content_already_has_pdf(content: str | None) -> bool:
	if not content:
		return False
	try:
		parsed = json.loads(content)
	except (ValueError, TypeError):
		return False
	for block in parsed.get("blocks") or []:
		if block.get("type") != "upload":
			continue
		data = block.get("data") or {}
		if (data.get("file_type") or "").upper() == "PDF" and data.get("file_url"):
			return True
	return False


def _find_pdf_for_course(course_name: str) -> str | None:
	"""Return the file_url of the most recently attached PDF on `course_name`."""
	rows = frappe.get_all(
		"File",
		filters={
			"attached_to_doctype": "LMS Course",
			"attached_to_name": course_name,
			"file_name": ["like", "%.pdf"],
		},
		fields=["file_url"],
		order_by="creation desc",
		limit_page_length=1,
	)
	return rows[0].file_url if rows else None


def _find_single_lesson(course_name: str) -> str | None:
	"""Return the lesson name if the course has exactly one Course Lesson."""
	lessons = frappe.get_all(
		"Course Lesson",
		filters={"course": course_name},
		fields=["name"],
		limit_page_length=2,
	)
	if len(lessons) != 1:
		return None
	return lessons[0].name


def run(dry_run: bool = False):
	resources = frappe.get_all(
		"LMS Course",
		filters={
			"course_type": "Resource",
			"resource_type": "Download",
		},
		fields=["name", "title"],
		order_by="creation asc",
	)
	print(
		f"Found {len(resources)} Download-type Resource courses "
		f"(dry_run={dry_run})..."
	)

	updated = []
	skipped_no_pdf = []
	skipped_multi_lesson = []
	skipped_already = []

	for course in resources:
		lesson_name = _find_single_lesson(course.name)
		if not lesson_name:
			skipped_multi_lesson.append(course.name)
			print(f"  skip (not single-lesson): {course.name}")
			continue

		pdf_url = _find_pdf_for_course(course.name)
		if not pdf_url:
			skipped_no_pdf.append(course.name)
			print(f"  skip (no attached PDF): {course.name}")
			continue

		existing_content = frappe.db.get_value("Course Lesson", lesson_name, "content")
		if _content_already_has_pdf(existing_content):
			skipped_already.append(course.name)
			print(f"  skip (already has PDF viewer): {course.name}")
			continue

		new_content = _build_pdf_content(pdf_url)
		# set_value bypasses optimistic-locking — File inserts during the
		# original populate run bumped the lesson's `modified` timestamp, so a
		# .save() here would TimestampMismatchError. Same trick as the original
		# populate script uses for LMS Course.image.
		frappe.db.set_value("Course Lesson", lesson_name, "content", new_content)
		updated.append(course.name)
		print(f"  updated: {course.name} (lesson={lesson_name}, pdf={pdf_url})")

	print(
		f"Done. updated={len(updated)}, "
		f"skipped_already={len(skipped_already)}, "
		f"skipped_no_pdf={len(skipped_no_pdf)}, "
		f"skipped_multi_lesson={len(skipped_multi_lesson)}"
	)

	if dry_run:
		frappe.db.rollback()
		print("Dry-run: rolled back.")
	else:
		frappe.db.commit()
		print("Committed.")

"""
One-off migration: populate 15 caregiver-audience "Free Resources" (PDF social
stories sourced from Caregiver Resources.csv).

Each row becomes a single-lesson Download Resource:
    LMS Course (course_type=Resource, resource_type=Download, audience='Parents / Caregivers')
    └─ Course Chapter
       └─ Course Lesson  (body = Markdown link to the PDF)

Thumbnails and PDFs are downloaded from the Duda CDN and saved as public Frappe
Files so the resources keep working if the source site changes.

Run with:

    docker exec lms-backend-1 bench --site devlms.ppt4ed.org execute lms.oneoff_populate_resources.run

Dry-run (rolls back at the end, but still hits the network for downloads):

    docker exec lms-backend-1 bench --site devlms.ppt4ed.org execute lms.oneoff_populate_resources.run --kwargs '{"dry_run": true}'

Idempotent: if a Resource with the same title already exists, it is skipped.
"""

import urllib.parse
import urllib.request

import frappe


CATEGORY = "Social Stories"
AUDIENCE = "Parents / Caregivers"

# Lesson body uses Markdown (Course Lesson.body is a Markdown Editor field).
LESSON_BODY_TEMPLATE = (
	"### {title}\n\n"
	"This printable social story is a free resource for parents and caregivers.\n\n"
	"[Download PDF]({pdf_url})\n"
)

DESCRIPTION_TEMPLATE = (
	"<p>{title} — a printable social story for parents and caregivers. "
	"Click the download link inside the resource to get the PDF.</p>"
)

SHORT_INTRO_TEMPLATE = "Printable social story for parents and caregivers."


# (title, thumbnail_url, pdf_url) — sourced from Caregiver Resources.csv
RESOURCES = [
	(
		"Turtle Breaths Social Story",
		"https://irp.cdn-website.com/029532b9/dms3rep/multi/Turtle+Breaths.png",
		"https://irp.cdn-website.com/029532b9/files/uploaded/turtle+breaths+social+story.pdf",
	),
	(
		"When Things Are Too Loud Social Story",
		"https://irp.cdn-website.com/029532b9/dms3rep/multi/When+Things+Are+Too+Loud.png",
		"https://irp.cdn-website.com/029532b9/files/uploaded/when+things+are+too+loud+social+story.pdf",
	),
	(
		"Understanding My Body Social Story",
		"https://irp.cdn-website.com/029532b9/dms3rep/multi/Screenshot+2026-04-02+120745.png",
		"https://irp.cdn-website.com/029532b9/files/uploaded/Understanding+my+body+social+story.pdf",
	),
	(
		"Mealtime Social Story",
		"https://irp.cdn-website.com/029532b9/dms3rep/multi/Screenshot+2026-04-02+120729.png",
		"https://irp.cdn-website.com/029532b9/files/uploaded/mealtime+social+story.pdf",
	),
	(
		"I Can Get My Nails Trimmed Social Story",
		"https://irp.cdn-website.com/029532b9/dms3rep/multi/Screenshot+2026-04-02+120713.png",
		"https://irp.cdn-website.com/029532b9/files/uploaded/I+Can+Get+my+Nails+Trimmed+Social+Story.pdf",
	),
	(
		"I Can Be Flexible At School Social Story",
		"https://irp.cdn-website.com/029532b9/dms3rep/multi/Cover+-+I+Can+Be+Flexible.png",
		"https://irp.cdn-website.com/029532b9/files/uploaded/I+Can+Be+Flexible+at+Home%21+Social+Story.pdf",
	),
	(
		"Being A Good Friend Social Story",
		"https://irp.cdn-website.com/029532b9/dms3rep/multi/Cover+-+Being+A+Good+Friend.png",
		"https://irp.cdn-website.com/029532b9/files/uploaded/Being+a+good+friend+social+story.pdf",
	),
	(
		"Helpful Habits Social Story",
		"https://irp.cdn-website.com/029532b9/dms3rep/multi/Cover+-+Helpful+Habits.png",
		"https://irp.cdn-website.com/029532b9/files/uploaded/Helpful+Habits+Social+Story+NEW.pdf",
	),
	(
		"Hurtful Habits Social Story",
		"https://irp.cdn-website.com/029532b9/dms3rep/multi/Cover+-+Hurtful+Habits.png",
		"https://irp.cdn-website.com/029532b9/files/uploaded/Hurtful+Habits+Social+Story+NEW.pdf",
	),
	(
		"I Can Be Flexible At Home Social Story",
		"https://irp.cdn-website.com/029532b9/dms3rep/multi/Cover+-+I+Can+Be+Flexible+At+Home.png",
		"https://irp.cdn-website.com/029532b9/files/uploaded/I+Can+Be+Flexible+at+Home%21+Social+Story.pdf",
	),
	(
		"I Can Take Turns Social Story",
		"https://irp.cdn-website.com/029532b9/dms3rep/multi/Cover+-+I+Can+Take+Turns.png",
		"https://irp.cdn-website.com/029532b9/files/uploaded/I+can+take+turns+social+story.pdf",
	),
	(
		"I Can Transition Social Story",
		"https://irp.cdn-website.com/029532b9/dms3rep/multi/Cover+-+I+Can+Transition.png",
		"https://irp.cdn-website.com/029532b9/files/uploaded/I+Can+Transition+Social+Story.pdf",
	),
	(
		"I Can Try Again Social Story",
		"https://irp.cdn-website.com/029532b9/dms3rep/multi/Cover+-+I+Can+Try+Again.png",
		"https://irp.cdn-website.com/029532b9/files/uploaded/I+can+try+again%21+Social+Story.pdf",
	),
	(
		"I Can Use Kind Words Social Story",
		"https://irp.cdn-website.com/029532b9/dms3rep/multi/Cover+-+I+Can+Use+Kind+Words.png",
		"https://irp.cdn-website.com/029532b9/files/uploaded/I+Can+Use+Kind+Words+Social+Story.pdf",
	),
	(
		"When I Get Frustrated Social Story",
		"https://irp.cdn-website.com/029532b9/dms3rep/multi/Cover+-+When+I+Get+Frustrated.png",
		"https://irp.cdn-website.com/029532b9/files/uploaded/When+I+Get+Frustrated.pdf",
	),
]


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _ensure_category():
	if not frappe.db.exists("LMS Category", CATEGORY):
		cat = frappe.new_doc("LMS Category")
		cat.category = CATEGORY
		cat.insert(ignore_permissions=True)
		print(f"  created LMS Category: {CATEGORY}")
	return CATEGORY


def _filename_from_url(url: str) -> str:
	"""Extract a clean filename from a CDN URL ('foo+bar.pdf' -> 'foo bar.pdf')."""
	last = url.rsplit("/", 1)[-1]
	# Decode URL escapes (+ → space, %21 → !, etc.)
	last = urllib.parse.unquote_plus(last)
	# Strip anything Frappe wouldn't like in a filename
	return last.replace("/", "_").strip() or "asset"


def _download_to_file(url: str, target_doctype: str, target_name: str) -> str:
	"""Fetch `url` and save it as a public Frappe File attached to the given doc.

	Returns the resulting `file_url` (e.g. '/files/foo.pdf').
	"""
	req = urllib.request.Request(url, headers={"User-Agent": "PPT4Ed-LMS/1.0"})
	with urllib.request.urlopen(req, timeout=60) as resp:
		content = resp.read()

	filename = _filename_from_url(url)
	file_doc = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": filename,
			"content": content,
			"decode": False,
			"is_private": 0,
			"attached_to_doctype": target_doctype,
			"attached_to_name": target_name,
		}
	)
	file_doc.insert(ignore_permissions=True)
	return file_doc.file_url


def _create_resource(title: str, thumbnail_url: str, pdf_url: str, category: str):
	# Skip if already imported (match on title, since slug is autogenerated).
	existing = frappe.db.exists("LMS Course", {"title": title, "course_type": "Resource"})
	if existing:
		print(f"  exists, skipping: {title} -> {existing}")
		return None

	# Create the LMS Course shell first so File rows can attach to it.
	course = frappe.new_doc("LMS Course")
	course.title = title
	course.course_type = "Resource"
	course.resource_type = "Download"
	course.audience = AUDIENCE
	course.category = category
	course.short_introduction = SHORT_INTRO_TEMPLATE
	course.description = DESCRIPTION_TEMPLATE.format(title=title)
	course.published = 1
	course.published_on = frappe.utils.today()
	# Suppress the daily "new course published" audience notification — these
	# 15 are bulk-imported, not individually announceable. An admin can flip
	# this back to 0 manually if they want to push a notification later.
	course.notification_sent = 1
	course.insert(ignore_permissions=True)

	# Download + attach assets.
	image_url = _download_to_file(thumbnail_url, "LMS Course", course.name)
	pdf_file_url = _download_to_file(pdf_url, "LMS Course", course.name)

	course.image = image_url
	course.save(ignore_permissions=True)

	# Single chapter + single lesson — single-lesson resources render the lesson
	# body inline on the resource page, so the PDF link is the entire content.
	chapter = frappe.new_doc("Course Chapter")
	chapter.course = course.name
	chapter.title = title
	chapter.insert(ignore_permissions=True)

	lesson = frappe.new_doc("Course Lesson")
	lesson.course = course.name
	lesson.chapter = chapter.name
	lesson.title = title
	lesson.body = LESSON_BODY_TEMPLATE.format(title=title, pdf_url=pdf_file_url)
	lesson.insert(ignore_permissions=True)

	chapter.append("lessons", {"lesson": lesson.name})
	chapter.save(ignore_permissions=True)

	course.append("chapters", {"chapter": chapter.name})
	course.save(ignore_permissions=True)

	print(f"  created: {course.name}  (image={image_url}, pdf={pdf_file_url})")
	return course.name


# ------------------------------------------------------------------
# Entrypoint
# ------------------------------------------------------------------


def run(dry_run: bool = False):
	print(f"Populating {len(RESOURCES)} caregiver resources (dry_run={dry_run})...")

	category = _ensure_category()
	created = []
	skipped = 0

	for title, thumb, pdf in RESOURCES:
		try:
			name = _create_resource(title, thumb, pdf, category)
		except Exception as e:
			print(f"  FAILED for {title!r}: {e}")
			raise
		if name:
			created.append(name)
		else:
			skipped += 1

	print(f"Done. created={len(created)}, skipped={skipped}")

	if dry_run:
		frappe.db.rollback()
		print("Dry-run: rolled back.")
	else:
		frappe.db.commit()
		print("Committed.")

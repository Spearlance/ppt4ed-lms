import frappe

from lms.lms.utils import ensure_instructors_have_moderator_role


def execute():
	"""Grant the Moderator role to every user who is an instructor on any
	LMS Course or LMS Event but doesn't yet hold the role.

	Bulk-imported instructors (e.g. courses populated via oneoff scripts
	or Frappe Desk imports) ended up in the Course Instructor child table
	without ever getting the Moderator role on their User. That makes
	them invisible to `lms.lms.api.search_users_by_role` (which filters
	for Moderator/LMS Student) and locks them out of the frontend Course
	editor (gated on `is_moderator`). Backfill so every existing
	instructor matches the implicit "instructor = Moderator" model.

	The shared helper inserts Has Role rows directly to avoid User.save()
	side effects (no welcome email, no password reset notification).
	"""
	instructor_users = frappe.get_all(
		"Course Instructor",
		filters={"parenttype": ["in", ["LMS Course", "LMS Event"]]},
		pluck="instructor",
		distinct=True,
	)
	ensure_instructors_have_moderator_role(instructor_users)

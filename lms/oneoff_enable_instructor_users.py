"""
One-off fix: enable instructor User accounts that were created disabled.

The initial course-upload CSV created `Course Instructor` rows pointing at
User records (Moderator role, full_name, bio, image all set) but left those
Users at `enabled=0` with no password set. The bios/images render on public
course pages either way (see `lms.lms.utils.get_instructors`), but the
instructors can't log in until enabled.

Per the 2026-05-12 launch-sprint scope: enable the accounts now, do NOT
send any invite/welcome/reset email. Garrett will hand off credentials per
instructor when ready.

This script:
  1. Finds every User who appears in `Course Instructor.instructor` on a
     `LMS Course` or `LMS Event` parent.
  2. Filters down to Users that hold the Moderator role and are currently
     `enabled=0`.
  3. Flips `enabled=1` via `frappe.db.set_value`, which bypasses
     `User.save()` so no notification / welcome email fires.

Run with:

    docker exec lms-backend-1 bench --site devlms.ppt4ed.org \\
        execute lms.oneoff_enable_instructor_users.run

Dry-run (prints what would change, rolls back). `bench execute --kwargs`
uses Python `eval`, so pass Python literals (`True`, not `true`):

    docker exec lms-backend-1 bench --site devlms.ppt4ed.org \\
        execute lms.oneoff_enable_instructor_users.run --kwargs '{"dry_run": True}'

Idempotent: instructors already at `enabled=1` are reported as skipped.
"""

import frappe


def _instructor_user_names() -> list[str]:
	rows = frappe.get_all(
		"Course Instructor",
		filters={"parenttype": ["in", ["LMS Course", "LMS Event"]]},
		pluck="instructor",
		distinct=True,
	)
	return sorted({r for r in rows if r})


def run(dry_run: bool = False):
	instructors = _instructor_user_names()
	print(
		f"Found {len(instructors)} distinct instructor User refs across "
		f"LMS Course + LMS Event (dry_run={dry_run})."
	)

	enabled_now = []
	skipped_already_enabled = []
	skipped_no_moderator = []
	skipped_missing_user = []

	for name in instructors:
		user = frappe.db.get_value(
			"User", name, ["enabled"], as_dict=True
		)
		if not user:
			skipped_missing_user.append(name)
			print(f"  skip (no User row): {name}")
			continue

		has_moderator = frappe.db.exists(
			"Has Role", {"parent": name, "role": "Moderator"}
		)
		if not has_moderator:
			skipped_no_moderator.append(name)
			print(f"  skip (no Moderator role): {name}")
			continue

		if user.enabled:
			skipped_already_enabled.append(name)
			print(f"  skip (already enabled): {name}")
			continue

		frappe.db.set_value("User", name, "enabled", 1)
		enabled_now.append(name)
		print(f"  enabled: {name}")

	print(
		f"Done. enabled={len(enabled_now)}, "
		f"already_enabled={len(skipped_already_enabled)}, "
		f"no_moderator_role={len(skipped_no_moderator)}, "
		f"missing_user={len(skipped_missing_user)}"
	)

	if dry_run:
		frappe.db.rollback()
		print("Dry-run: rolled back.")
	else:
		frappe.db.commit()
		print("Committed.")

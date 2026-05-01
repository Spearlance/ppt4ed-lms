from lms.install import give_email_template_permission


def execute():
	"""Grant Email Template CRUD perms to Moderator + Global Admin so they
	can edit transactional templates from /lms Settings → Email Templates.

	Default Frappe ships only System Manager (full) + Desk User (read).
	Idempotent: skips roles that already have a Custom DocPerm row.
	"""
	give_email_template_permission()

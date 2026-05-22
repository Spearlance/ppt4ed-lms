import frappe


def execute():
	"""Lower System Settings.minimum_password_score to 1 (lenient).

	Frappe's update_password / test_password_strength endpoints score
	passwords with zxcvbn on a 0-4 scale and reject anything below
	minimum_password_score. Pre-launch the live value was set strict
	enough that ordinary users with memorable passwords (e.g.
	'spring2026', 'bluefish99') were rejected on the invite-accept and
	reset-password flows.

	Our own signup paths already pass ignore_password_policy=True, but
	Frappe's /update-password page (where reset-email recipients land)
	honors this System Settings value, so it still bites.

	Score 1 rejects only the obviously-weak ('password', '12345678',
	'qwerty') while letting reasonable memorable passwords through. Our
	hard 8-character minimum in the signup endpoints is unchanged.
	"""
	frappe.db.set_single_value("System Settings", "minimum_password_score", 1)

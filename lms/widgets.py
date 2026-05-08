"""The widgets provides access to HTML widgets
provided in each frappe module.

Widgets are simple moduler templates that can reused
in multiple places. These are like macros, but accessing
them will be a lot easier.

The widgets will be provided
"""

import frappe
from frappe import _
from frappe.utils import getdate
from frappe.utils.jinja import get_jenv

from lms.lms.utils import get_lms_path

# search path for widgets.
# When {{widgets.SomeWidget()}} is called, it looks for
# widgets/SomeWidgets.html in each of these modules.
MODULES = [
	"lms",
]


def update_website_context(context):
	"""Adds widgets to the context.

	Called from hooks.
	"""
	context.widgets = Widgets()
	_customize_navbar_and_footer(context)


def _customize_navbar_and_footer(context):
	"""Replace Frappe's stock navbar/footer defaults with PPT4ed-shaped values.

	- "My Account" in the post-login dropdown points at the Vue LMS profile
	  (`/lms/user/<username>`) instead of Frappe's desk-side `/me` page —
	  PPT4ed admins have ZERO Desk access (see CLAUDE.md admin-surface rule).
	  "Switch To Desk" is hidden via CSS in `style.css`.
	- Footer is populated with PPT4ed legal pages and a GitHub icon link
	  (AGPL §13 source-availability) — Built on Frappe is suppressed.
	"""
	lms_path = get_lms_path()

	user = frappe.session.user
	username = None
	if user and user != "Guest":
		username = frappe.db.get_value("User", user, "username")
	profile_url = f"/{lms_path}/user/{username}" if username else f"/{lms_path}"

	context.post_login = [
		{"label": _("My Account"), "url": profile_url},
		{"label": _("Log out"), "url": "/logout"},
	]

	# Truthy single-space suppresses the included `footer_powered.html` partial
	# without leaving a visible `Built on Frappe` line.
	context.footer_powered = " "

	if not context.get("copyright"):
		context.copyright = f"{getdate().year} PPT4ed"

	context.footer_items = [
		{"label": _("Privacy Policy"), "url": f"/{lms_path}/privacy"},
		{"label": _("Terms of Service"), "url": f"/{lms_path}/terms"},
		{"label": _("Cookie Policy"), "url": f"/{lms_path}/cookies"},
		{
			"label": _("Source Code (AGPL v3)"),
			"url": "https://github.com/Spearlance/ppt4ed-lms",
			"icon": "/assets/lms/images/github-mark.svg",
			"open_in_new_tab": 1,
			"right": 1,
		},
	]


class Widgets:
	"""The widget collection.

	This is just a placeholder object and returns the appropriate
	widget when accessed using attribute.

	    >>> widgets = Widgets()
	    >>> widgets.HelloWorld(name="World!")
	    '<div>Hello, World!</div>'
	"""

	def __getattr__(self, name):
		widget_globals = {"widgets": self}
		if not name.startswith("__"):
			return Widget(name, widget_globals)
		else:
			raise AttributeError(name)


class Widget:
	"""The Widget class renders a widget.

	Widget is a reusable template defined in widgets/ directory in
	each frappe module.

	    >>> w = Widget("HelloWorld")
	    >>> w(name="World!")
	    '<div>Hello, World!</div>'
	"""

	def __init__(self, name, widget_globals):
		if not widget_globals:
			widget_globals = {}

		self.widget_globals = widget_globals
		self.name = name

	def __call__(self, **kwargs):
		# the widget could be in any of the modules
		paths = [f"{module}/widgets/{self.name}.html" for module in MODULES]
		env = get_jenv()
		kwargs.update(self.widget_globals)
		return env.get_or_select_template(paths).render(kwargs)

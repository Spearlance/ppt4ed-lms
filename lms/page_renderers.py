"""Custom page renderers for LMS app.

Handles rendering of profile pages.
"""

import mimetypes
import os

import frappe
from frappe.website.page_renderers.base_renderer import BaseRenderer
from frappe.www.printview import validate_print_permission
from werkzeug.wrappers import Response
from werkzeug.wsgi import wrap_file

CERTIFICATE_ROUTE_PREFIX = "certificate/"


class CertificateRenderer(BaseRenderer):
	"""Serve a certificate PDF from a clean, query-string-free URL.

	The standard download link is
	`/api/method/frappe.utils.print_format.download_pdf?doctype=LMS+Certificate&...`,
	which some ad/content blockers match against their filter lists and cancel
	client-side (ERR_BLOCKED_BY_CLIENT). This renderer exposes the same PDF at
	`/certificate/<name>` — a first-party path with no `download_pdf` token and no
	query string — so certificate email links survive aggressive blockers.

	A www page controller cannot return a binary body (the TemplatePage renderer
	always renders HTML and ignores frappe.local.response.type), so streaming the
	PDF requires a custom page_renderer registered via the `page_renderer` hook.
	"""

	def can_render(self):
		# Cheap string gate first — can_render runs on every website request, so
		# only touch the DB for paths that actually look like a certificate link.
		if not self.path.startswith(CERTIFICATE_ROUTE_PREFIX):
			return False
		name = self._certificate_name()
		return bool(name) and frappe.db.exists("LMS Certificate", name)

	def render(self):
		name = self._certificate_name()

		doc = frappe.get_doc("LMS Certificate", name)
		# Identical access rules to frappe.utils.print_format.download_pdf: owner,
		# moderator, published (website permission) or a valid share key all pass;
		# anyone else gets the framework's permission failure (login / 403).
		validate_print_permission(doc)

		print_format = frappe.db.get_value("LMS Certificate", name, "template")
		pdf_generator = (
			frappe.db.get_value("Print Format", print_format, "pdf_generator") or "chrome"
		)
		pdf_bytes = frappe.get_print(
			"LMS Certificate",
			name,
			print_format,
			as_pdf=True,
			pdf_generator=pdf_generator,
		)

		response = Response()
		response.mimetype = "application/pdf"
		response.headers["Content-Disposition"] = f'inline; filename="{name}.pdf"'
		response.data = pdf_bytes
		return response

	def _certificate_name(self):
		return self.path[len(CERTIFICATE_ROUTE_PREFIX):].strip("/")


class SCORMRenderer(BaseRenderer):
	def can_render(self):
		return "scorm/" in self.path

	def render(self):
		path = os.path.join(frappe.local.site_path, "public", self.path.lstrip("/"))

		extension = os.path.splitext(path)[1]
		if not extension:
			path = f"{path}.html"

		# check if path exists and is actually a file and not a folder
		if os.path.exists(path) and os.path.isfile(path):
			f = open(path, "rb")
			response = Response(wrap_file(frappe.local.request.environ, f), direct_passthrough=True)
			response.mimetype = mimetypes.guess_type(path)[0]
			return response
		else:
			path = path.replace(".html", "")
			if os.path.exists(path) and os.path.isdir(path):
				index_path = os.path.join(path, "index.html")
				if os.path.exists(index_path):
					f = open(index_path, "rb")
					response = Response(wrap_file(frappe.local.request.environ, f), direct_passthrough=True)
					response.mimetype = mimetypes.guess_type(index_path)[0]
					return response
			elif not os.path.exists(path):
				chapter_folder = "/".join(self.path.split("/")[:3])
				chapter_folder_path = os.path.realpath(frappe.get_site_path("public", chapter_folder))
				file = path.split("/")[-1]
				correct_file_path = None

				for root, _dirs, files in os.walk(chapter_folder_path):
					if file in files:
						correct_file_path = os.path.join(root, file)
						break

				if correct_file_path:
					f = open(correct_file_path, "rb")
					response = Response(wrap_file(frappe.local.request.environ, f), direct_passthrough=True)
					response.mimetype = mimetypes.guess_type(correct_file_path)[0]
					return response

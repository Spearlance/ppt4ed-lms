"""Event materials: handouts (PDFs, images) attached to an LMS Event.

Files are stored private. Registered attendees never get the raw
/private/files URL; they read a material through `view_event_material`, which
checks registration and serves the bytes inline so the LMS can show the file
in-page instead of forcing a download.

Admin actions gate on `can_modify_event` and then bypass doctype permissions,
because Global Admins and event instructors are not reliably covered by the
permission rows.
"""

import mimetypes
import os
import re

import frappe
from frappe import _
from werkzeug.wrappers import Response

from lms.lms.utils import can_modify_event

DOCTYPE = "LMS Event Material"

# extension -> how the frontend displays it
VIEWABLE_EXTENSIONS = {
	"pdf": "pdf",
	"png": "image",
	"jpg": "image",
	"jpeg": "image",
	"gif": "image",
}


def _extension(file_url):
	return os.path.splitext(file_url or "")[1].lstrip(".").lower()


def is_registered(event, user=None):
	user = user or frappe.session.user
	if user == "Guest":
		return False
	return bool(frappe.db.exists("LMS Event Registration", {"event": event, "member": user}))


def can_view_materials(event):
	if frappe.session.user == "Guest":
		return False
	return can_modify_event(event) or is_registered(event)


def _require_admin(event):
	if frappe.session.user == "Guest" or not can_modify_event(event):
		frappe.throw(
			_("You do not have permission to manage materials for this event."),
			frappe.PermissionError,
		)


def _get_material(name):
	material = frappe.db.get_value(
		DOCTYPE, name, ["name", "event", "title", "file", "sort_order"], as_dict=True
	)
	if not material:
		frappe.throw(_("Material not found."), frappe.DoesNotExistError)
	return material


def _serialize(material):
	return {
		"name": material.name,
		"title": material.title,
		"file_type": VIEWABLE_EXTENSIONS.get(_extension(material.file), "other"),
		"extension": _extension(material.file),
	}


def count_event_materials(event):
	return frappe.db.count(DOCTYPE, {"event": event})


@frappe.whitelist()
def get_event_materials(event: str):
	if not can_view_materials(event):
		frappe.throw(
			_("Materials are available to registered attendees only."),
			frappe.PermissionError,
		)
	rows = frappe.get_all(
		DOCTYPE,
		filters={"event": event},
		fields=["name", "event", "title", "file", "sort_order"],
		order_by="sort_order asc, creation asc",
	)
	return [_serialize(row) for row in rows]


@frappe.whitelist(methods=["POST"])
def add_event_material(event: str, title: str, file: str):
	"""Attach an already-uploaded private File (by File docname) to the event."""
	_require_admin(event)
	if not frappe.db.exists("LMS Event", event):
		frappe.throw(_("Event not found."), frappe.DoesNotExistError)

	title = (title or "").strip()
	if not title:
		frappe.throw(_("Please give the material a name."))

	file_doc = frappe.db.get_value(
		"File",
		file,
		["name", "file_url", "is_private", "owner", "attached_to_doctype", "attached_to_name"],
		as_dict=True,
	)
	# Only the uploader may turn their own fresh upload into a material;
	# otherwise this endpoint could be used to re-home someone else's file.
	if not file_doc or file_doc.owner != frappe.session.user or file_doc.attached_to_name:
		frappe.throw(_("Uploaded file not found. Please upload it again."))
	if not file_doc.is_private:
		frappe.throw(_("Event materials must be uploaded as private files."))
	if _extension(file_doc.file_url) not in VIEWABLE_EXTENSIONS:
		frappe.throw(_("Only PDF, PNG, JPG and GIF files can be added as materials."))

	last = frappe.get_all(
		DOCTYPE, filters={"event": event}, pluck="sort_order", order_by="sort_order desc", limit=1
	)
	material = frappe.get_doc(
		{
			"doctype": DOCTYPE,
			"event": event,
			"title": title,
			"file": file_doc.file_url,
			"sort_order": (last[0] if last else 0) + 1,
		}
	)
	material.insert(ignore_permissions=True)
	frappe.db.set_value(
		"File",
		file_doc.name,
		{
			"attached_to_doctype": DOCTYPE,
			"attached_to_name": material.name,
			"attached_to_field": "file",
		},
	)
	return _serialize(material)


@frappe.whitelist(methods=["POST"])
def rename_event_material(name: str, title: str):
	material = _get_material(name)
	_require_admin(material.event)
	title = (title or "").strip()
	if not title:
		frappe.throw(_("Please give the material a name."))
	frappe.db.set_value(DOCTYPE, name, "title", title)
	material.title = title
	return _serialize(material)


@frappe.whitelist(methods=["POST"])
def delete_event_material(name: str):
	material = _get_material(name)
	_require_admin(material.event)
	frappe.delete_doc(DOCTYPE, name, ignore_permissions=True)
	return name


@frappe.whitelist(methods=["POST"])
def reorder_event_materials(event: str, names: str | list):
	"""Persist a new order. `names` is the full list of material names, first to last."""
	_require_admin(event)
	names = frappe.parse_json(names) or []
	existing = set(frappe.get_all(DOCTYPE, filters={"event": event}, pluck="name"))
	position = 0
	for name in names:
		if name not in existing:
			continue
		position += 1
		frappe.db.set_value(DOCTYPE, name, "sort_order", position, update_modified=False)
	return get_event_materials(event)


def delete_materials_for_event(event):
	"""Called when an event is deleted, so no private files are orphaned."""
	for name in frappe.get_all(DOCTYPE, filters={"event": event}, pluck="name"):
		frappe.delete_doc(DOCTYPE, name, ignore_permissions=True, force=True)


@frappe.whitelist(methods=["GET"])
def view_event_material(name: str, download: str | int | None = None):
	"""Serve a material's bytes to an admin or registered attendee.

	Inline by default (so the in-app viewer can render it); `download=1`
	switches to an attachment for people who want to print or keep a copy.
	"""
	material = _get_material(name)
	if not can_view_materials(material.event):
		frappe.throw(
			_("Materials are available to registered attendees only."),
			frappe.PermissionError,
		)

	extension = _extension(material.file)
	if extension not in VIEWABLE_EXTENSIONS:
		frappe.throw(_("This file type cannot be displayed."))

	file_name = frappe.db.get_value(
		"File",
		{
			"file_url": material.file,
			"attached_to_doctype": DOCTYPE,
			"attached_to_name": material.name,
		},
		"name",
	)
	if not file_name:
		frappe.throw(_("File not found."), frappe.DoesNotExistError)

	path = frappe.get_doc("File", file_name).get_full_path()
	if not os.path.isfile(path):
		frappe.throw(_("File not found."), frappe.DoesNotExistError)
	with open(path, "rb") as handle:
		content = handle.read()

	mimetype = mimetypes.guess_type(f"file.{extension}")[0] or "application/octet-stream"
	response = Response(content, mimetype=mimetype)
	disposition = "attachment" if frappe.utils.cint(download) else "inline"
	safe_title = re.sub(r"[^A-Za-z0-9._-]+", "-", material.title).strip("-.") or "material"
	response.headers.set("Content-Disposition", disposition, filename=f"{safe_title}.{extension}")
	response.headers.set("Cache-Control", "private, max-age=3600")
	response.headers.set("X-Content-Type-Options", "nosniff")
	return response

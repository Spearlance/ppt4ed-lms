import frappe

from lms.install import create_global_admin_role


def execute():
	create_global_admin_role()

# Copyright (c) 2026, PPT4Ed and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class CertificateSigner(Document):
	"""Child row of LMS Course.certificate_signers: a User whose signature
	block prints on the course's certificate. Max two per course, one per
	discipline (validated in LMSCourse.validate_certificate_signers)."""

	pass

import frappe
from frappe.model.document import Document
from frappe.utils import random_string


class Patient(Document):
	pass


def _pw_installed():
	return frappe.db.table_exists("PW Bed Allotment")


def _find_active_allotment(customer_name):
	"""Return the active PW Bed Allotment name for a customer, or None."""
	if not _pw_installed():
		return None
	return frappe.db.get_value(
		"PW Bed Allotment",
		{"patient": customer_name, "status": "Active"},
		"name",
	)


def sync_from_customer(doc, method=None):
	"""Called on Customer.on_update.
	When pc_nursing_center is set and customer has an active allotment, ensure a portal token exists.
	When pc_nursing_center is cleared, revoke the token.
	"""
	if not _pw_installed():
		return

	nursing_center = doc.get("pc_nursing_center")
	if nursing_center and _find_active_allotment(doc.name):
		if not doc.get("pc_access_token"):
			frappe.db.set_value("Customer", doc.name, "pc_access_token", random_string(32))
	elif not nursing_center:
		frappe.db.set_value("Customer", doc.name, "pc_access_token", None)


def sync_from_allotment(doc, method=None):
	"""Called on PW Bed Allotment.on_update.
	On discharge / transfer: clear nursing center and token on Customer so the portal is immediately revoked.
	"""
	if not _pw_installed():
		return

	if doc.status and doc.status.lower() not in ("active",):
		update = {"pc_nursing_center": None, "pc_access_token": None}
		try:
			if "pc_device_id" in frappe.db.get_table_columns("Customer"):
				update["pc_device_id"] = None
		except Exception:
			pass
		frappe.db.set_value("Customer", doc.patient, update)

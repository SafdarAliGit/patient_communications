import uuid
import frappe
from frappe import _


def _get_site_title():
	try:
		title = frappe.db.get_single_value("Website Settings", "title")
		if title:
			return title
	except Exception:
		pass
	try:
		title = frappe.db.get_single_value("System Settings", "app_title")
		if title:
			return title
	except Exception:
		pass
	return "Patient Portal"


def get_context(context):
	context.no_cache = 1
	context.full_width = 1

	context.site_title = _get_site_title()

	token = frappe.form_dict.get("token")

	context.patient = None
	context.access_token = token or ""
	context.large_touch = frappe.form_dict.get("large") == "1"
	context.new_device_id = None
	context.device_locked = False

	if not token:
		return

	from patient_communications.api import _get_active_allotment

	name = frappe.db.get_value("Customer", {"pc_access_token": token}, "name")
	if not name:
		return

	nc = frappe.db.get_value("Customer", name, "pc_nursing_center")
	if not nc or not _get_active_allotment(name):
		return

	# Device locking: bind on first access, validate on subsequent requests
	# (only enforced after bench migrate has added the pc_device_id column)
	try:
		cols = frappe.db.get_table_columns("Customer")
		device_field_ready = "pc_device_id" in cols
	except Exception:
		device_field_ready = False

	if device_field_ready:
		stored_device_id = frappe.db.get_value("Customer", name, "pc_device_id")
		request_device_id = frappe.request.cookies.get("pc_device_id") if frappe.request else None

		if not stored_device_id:
			# First access — bind this device
			new_device_id = str(uuid.uuid4())
			frappe.db.set_value("Customer", name, "pc_device_id", new_device_id, update_modified=False)
			frappe.db.commit()
			context.new_device_id = new_device_id
		elif request_device_id != stored_device_id:
			# Different device — block access
			context.device_locked = True
			return

	customer = frappe.db.get_value(
		"Customer", name,
		["name", "customer_name", "pc_nursing_center"],
		as_dict=True,
	)
	if customer:
		context.patient = {
			"name": customer.name,
			"patient_name": customer.customer_name,
			"nursing_station": customer.pc_nursing_center,
		}

import frappe

ROLES = ["Nursing Station Staff"]


def after_install():
	create_roles()
	_add_customer_fields()
	_add_pw_clinic_settings_fields()


def create_roles():
	for role_name in ROLES:
		if frappe.db.exists("Role", role_name):
			continue
		role = frappe.new_doc("Role")
		role.role_name = role_name
		role.desk_access = 0
		role.insert(ignore_permissions=True)


def _add_customer_fields():
	"""Add custom fields to Customer — always required."""
	if not frappe.db.exists("Custom Field", "Customer-pc_nursing_center"):
		frappe.get_doc({
			"doctype": "Custom Field",
			"dt": "Customer",
			"fieldname": "pc_nursing_center",
			"fieldtype": "Link",
			"label": "Nursing Center",
			"options": "Nursing Station",
			"description": "Assign the nursing center for this patient's communications. A portal link is auto-generated after assignment.",
			"insert_after": "customer_name",
		}).insert(ignore_permissions=True)

	if not frappe.db.exists("Custom Field", "Customer-pc_access_token"):
		frappe.get_doc({
			"doctype": "Custom Field",
			"dt": "Customer",
			"fieldname": "pc_access_token",
			"fieldtype": "Data",
			"label": "PC Portal Token",
			"hidden": 1,
			"read_only": 1,
			"insert_after": "pc_nursing_center",
		}).insert(ignore_permissions=True)

	if not frappe.db.exists("Custom Field", "Customer-pc_device_id"):
		frappe.get_doc({
			"doctype": "Custom Field",
			"dt": "Customer",
			"fieldname": "pc_device_id",
			"fieldtype": "Data",
			"label": "PC Bound Device",
			"hidden": 1,
			"read_only": 1,
			"insert_after": "pc_access_token",
		}).insert(ignore_permissions=True)

	frappe.db.commit()


def _add_pw_clinic_settings_fields():
	"""Add optional fields to PW Clinic Settings if that app is installed."""
	if not frappe.db.table_exists("PW Clinic Settings"):
		return

	if not frappe.db.exists("Custom Field", "PW Clinic Settings-sb_patient_comms"):
		frappe.get_doc({
			"doctype": "Custom Field",
			"dt": "PW Clinic Settings",
			"fieldname": "sb_patient_comms",
			"fieldtype": "Section Break",
			"label": "Patient Communications",
			"insert_after": "enable_erpnext",
		}).insert(ignore_permissions=True)

	if not frappe.db.exists("Custom Field", "PW Clinic Settings-enable_patient_communications"):
		frappe.get_doc({
			"doctype": "Custom Field",
			"dt": "PW Clinic Settings",
			"fieldname": "enable_patient_communications",
			"fieldtype": "Check",
			"label": "Enable Patient Communications",
			"default": "0",
			"description": "Allow IPD patients to communicate with their assigned nursing center via a secure portal link.",
			"depends_on": "eval:doc.enable_ward_management",
			"insert_after": "sb_patient_comms",
		}).insert(ignore_permissions=True)

	frappe.db.commit()

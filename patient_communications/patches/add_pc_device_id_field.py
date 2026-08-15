import frappe


def execute():
	if frappe.db.exists("Custom Field", "Customer-pc_device_id"):
		return
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

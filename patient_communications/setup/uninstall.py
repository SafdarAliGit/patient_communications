import frappe

_CUSTOM_FIELDS = [
	("PW Clinic Settings", "sb_patient_comms"),
	("PW Clinic Settings", "enable_patient_communications"),
	("Customer", "pc_nursing_center"),
	("Customer", "pc_access_token"),
]


def before_uninstall():
	_remove_pw_integration_fields()


def _remove_pw_integration_fields():
	for dt, fieldname in _CUSTOM_FIELDS:
		cf_name = f"{dt}-{fieldname}"
		if frappe.db.exists("Custom Field", cf_name):
			frappe.delete_doc("Custom Field", cf_name, ignore_permissions=True)
	frappe.db.commit()

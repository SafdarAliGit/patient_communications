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

	if not token:
		return

	name = frappe.db.get_value("Customer", {"pc_access_token": token}, "name")
	if not name:
		return

	nc = frappe.db.get_value("Customer", name, "pc_nursing_center")
	if not nc:
		return

	# Device binding is intentionally NOT done here.
	# Link-preview bots (WhatsApp, Telegram, iMessage…) fetch this page
	# server-side without running JavaScript.  If we bound the device here,
	# the bot would consume the first-open slot and lock out the real patient.
	# Binding is handled by the client-side claim_device_token API call in
	# index.html, which only real browsers (that run JS) can trigger.
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

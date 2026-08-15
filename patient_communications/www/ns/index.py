import re
import frappe


def _slugify(value):
	value = (value or "").strip().lower()
	return re.sub(r"[^a-z0-9]+", "-", value).strip("-")


def get_context(context):
	context.no_cache = 1
	context.full_width = 1

	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/ns"
		raise frappe.Redirect

	stations = frappe.get_all(
		"Nursing Station",
		filters={"is_active": 1},
		fields=["name", "nursing_station_name", "ward_floor", "abbreviation"],
		order_by="nursing_station_name asc",
	)

	for s in stations:
		s["slug"] = _slugify(s.abbreviation) or _slugify(s.nursing_station_name)
		s["url"] = f"/ns/{s['slug']}"

	context.stations = stations

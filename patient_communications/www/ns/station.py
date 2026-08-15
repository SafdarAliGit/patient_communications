import re

import frappe


def _slugify(value):
	value = (value or "").strip().lower()
	return re.sub(r"[^a-z0-9]+", "-", value).strip("-")


def get_context(context):
	context.no_cache = 1
	context.full_width = 1

	slug = frappe.form_dict.get("station") or ""

	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = f"/login?redirect-to=/ns/{slug}"
		raise frappe.Redirect

	# Any authenticated staff member can open a station by slug
	all_stations = frappe.get_all(
		"Nursing Station",
		filters={"is_active": 1},
		fields=["name", "nursing_station_name", "ward_floor", "abbreviation"],
	)
	station = None
	for s in all_stations:
		s_slug = _slugify(s.abbreviation) or _slugify(s.nursing_station_name)
		if s_slug.lower() == slug.lower():
			station = s
			break

	context.station = station

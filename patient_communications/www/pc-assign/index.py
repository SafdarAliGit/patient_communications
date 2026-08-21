import frappe

_AVATAR_COLORS = ["#3d5a99", "#3d8f86", "#7266a6", "#b8823d", "#a8506f", "#4f8f63"]


def _avatar_color(name):
	h = 0
	for c in (name or ""):
		h = (h * 31 + ord(c)) & 0xFFFFFFFF
	return _AVATAR_COLORS[h % len(_AVATAR_COLORS)]


def _initials(name):
	parts = (name or "").split()
	return "".join(p[0].upper() for p in parts[:2] if p)


def get_context(context):
	context.no_cache = 1
	context.full_width = 1

	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/pc-assign"
		raise frappe.Redirect

	from patient_communications.api import _pw_installed

	try:
		from prescription_writter.utils import get_pac_for_user
		pac = get_pac_for_user(frappe.session.user)
		if not pac.get("show_pc_assign"):
			frappe.local.flags.redirect_location = "/pw-home"
			raise frappe.Redirect(302)
	except ImportError:
		from patient_communications.api import _STAFF_ROLES
		if not (set(frappe.get_roles(frappe.session.user)) & _STAFF_ROLES):
			context.not_authorized = True
			context.patients = []
			context.nursing_stations = []
			return

	context.not_authorized = False

	context.nursing_stations = frappe.get_all(
		"Nursing Station",
		filters={"is_active": 1},
		fields=["name", "nursing_station_name", "ward_floor"],
		order_by="nursing_station_name asc",
	)

	patients = []
	if _pw_installed():
		allotments = frappe.get_all(
			"PW Bed Allotment",
			filters={"status": "Active"},
			fields=["name", "patient", "bed", "room"],
			order_by="creation desc",
			ignore_permissions=True,
		)
		site_url = frappe.utils.get_url().rstrip("/")
		seen_customers = set()
		for a in allotments:
			if not a.patient or a.patient in seen_customers:
				continue
			seen_customers.add(a.patient)

			customer = frappe.db.get_value(
				"Customer", a.patient,
				["name", "customer_name", "pc_nursing_center", "pc_access_token"],
				as_dict=True,
			)
			if not customer:
				continue

			room_no, bed_no = "", ""
			try:
				if a.room:
					room_no = frappe.db.get_value("PW Ward Room", a.room, "room_name") or ""
				if a.bed:
					bed_no = frappe.db.get_value("PW Ward Bed", a.bed, "bed_number") or ""
			except Exception:
				pass

			token = customer.pc_access_token
			portal_url = f"{site_url}/patient?token={token}" if token and customer.pc_nursing_center else ""

			patients.append({
				"name": customer.name,
				"patient_name": customer.customer_name,
				"nursing_center": customer.pc_nursing_center or "",
				"room_no": room_no,
				"bed_no": bed_no,
				"portal_url": portal_url,
				"has_link": bool(token and customer.pc_nursing_center),
				"avatar_color": _avatar_color(customer.name),
				"initials": _initials(customer.customer_name),
			})

		patients.sort(key=lambda x: x["patient_name"] or "")

	context.patients = patients

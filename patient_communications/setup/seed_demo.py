import frappe


def run():
	"""Create demo Nursing Stations and Patients for local testing.
	Usage: bench --site <site> execute patient_communications.setup.seed_demo.run
	"""
	frappe.set_user("Administrator")

	stations = [
		{"nursing_station_name": "Ward A - ICU", "ward_floor": "2nd Floor", "abbreviation": "ICU", "email": "icu.station@pc.test"},
		{"nursing_station_name": "Ward B - General", "ward_floor": "3rd Floor", "abbreviation": "GEN", "email": "gen.station@pc.test"},
	]
	station_names = {}
	for s in stations:
		if frappe.db.exists("Nursing Station", s["nursing_station_name"]):
			station_names[s["abbreviation"]] = s["nursing_station_name"]
			continue
		doc = frappe.get_doc({"doctype": "Nursing Station", **s})
		doc.insert(ignore_permissions=True)
		station_names[s["abbreviation"]] = doc.name

	patients = [
		{"patient_name": "Ali Raza", "room_no": "201", "bed_no": "B1", "email": "ali.raza@pc.test", "station": "ICU"},
		{"patient_name": "Sara Khan", "room_no": "305", "bed_no": "B2", "email": "sara.khan@pc.test", "station": "GEN"},
	]
	for p in patients:
		if frappe.db.exists("Patient", {"patient_name": p["patient_name"]}):
			continue
		doc = frappe.get_doc(
			{
				"doctype": "Patient",
				"patient_name": p["patient_name"],
				"room_no": p["room_no"],
				"bed_no": p["bed_no"],
				"email": p["email"],
				"nursing_station": station_names[p["station"]],
				"is_active": 1,
			}
		)
		doc.insert(ignore_permissions=True)

	# Set known passwords for demo logins
	from frappe.utils.password import update_password

	for email in ["icu.station@pc.test", "gen.station@pc.test", "ali.raza@pc.test", "sara.khan@pc.test"]:
		if frappe.db.exists("User", email):
			update_password(email, "demo1234")

	frappe.db.commit()
	print("Seeded demo data. Logins (password: demo1234):")
	print(" Nursing Station (ICU): icu.station@pc.test")
	print(" Nursing Station (GEN): gen.station@pc.test")
	print(" Patient (ICU/201):     ali.raza@pc.test")
	print(" Patient (GEN/305):     sara.khan@pc.test")

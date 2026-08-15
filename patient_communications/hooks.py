app_name = "patient_communications"
app_title = "Patient Communications"
app_publisher = "Safdar Ali"
app_description = "Realtime text and browser voice-to-text communication between IPD patients and nursing stations"
app_email = "safdar211@gmail.com"
app_license = "mit"

# Website route rules
website_route_rules = [
	{"from_route": "/ns/<station>", "to_route": "ns/station"},
]

# Installation / uninstallation
after_install = "patient_communications.setup.install.after_install"
before_uninstall = "patient_communications.setup.uninstall.before_uninstall"

# DocType Events
doc_events = {
	"Customer": {
		"on_update": "patient_communications.patient_communications.doctype.patient.patient.sync_from_customer",
	},
	"PW Bed Allotment": {
		"on_update": "patient_communications.patient_communications.doctype.patient.patient.sync_from_allotment",
	},
}

# Inject "Send Patient Comms Link" button into PW Bed Allotment form
doctype_js = {
	"PW Bed Allotment": "public/js/pw_bed_allotment_hooks.js",
	"Customer": "public/js/customer_hooks.js",
}

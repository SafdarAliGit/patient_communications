import frappe
from frappe import _
from frappe.utils import now_datetime, random_string


# ── Helpers ──────────────────────────────────────────────────────────────────

def _pw_installed():
	return frappe.db.table_exists("PW Bed Allotment")


def _device_field_ready():
	"""True only after bench migrate has added the pc_device_id column to Customer."""
	try:
		return "pc_device_id" in frappe.db.get_table_columns("Customer")
	except Exception:
		return False


def _get_active_allotment(customer_name):
	if not _pw_installed():
		return None
	return frappe.db.get_value(
		"PW Bed Allotment",
		{"patient": customer_name, "status": "Active"},
		"name",
	)


_STAFF_ROLES = {"System Manager", "PW Admin", "PW DEO", "PW Doctor", "Nursing Station Staff", "Administrator"}


def _assert_staff(user):
	"""Raise PermissionError if the user is not recognised clinic staff."""
	if not (set(frappe.get_roles(user)) & _STAFF_ROLES):
		frappe.throw(_("Not authorized"), frappe.PermissionError)


def _assert_station(station_name):
	"""Raise if station doesn't exist or is inactive."""
	if not frappe.db.exists("Nursing Station", {"name": station_name, "is_active": 1}):
		frappe.throw(_("Nursing station not found or inactive"), frappe.DoesNotExistError)


def _build_patient_payload(customer_name):
	c = frappe.db.get_value(
		"Customer", customer_name,
		["name", "customer_name", "pc_nursing_center", "pw_patient_id"],
		as_dict=True,
	)
	nursing_station = c.pc_nursing_center
	allotment_name = _get_active_allotment(customer_name)
	room_no, bed_no, floor_no = "", "", ""
	if allotment_name:
		bed_info = frappe.db.get_value(
			"PW Bed Allotment", allotment_name, ["bed", "room", "floor"], as_dict=True
		) or frappe._dict()
		floor_no = bed_info.get("floor") or ""
		if bed_info.get("room"):
			room_no = frappe.db.get_value("PW Ward Room", bed_info.room, "room_name") or ""
		if bed_info.get("bed"):
			bed_no = frappe.db.get_value("PW Ward Bed", bed_info.bed, "bed_number") or ""

	station = frappe.db.get_value(
		"Nursing Station", nursing_station,
		["nursing_station_name", "ward_floor"], as_dict=True,
	) if nursing_station else None

	return {
		"name": c.name,
		"patient_name": c.customer_name,
		"mr_no": c.pw_patient_id or "",
		"nursing_station": nursing_station,
		"floor_no": floor_no,
		"room_no": room_no,
		"bed_no": bed_no,
		"station_name": station.nursing_station_name if station else None,
		"station_ward_floor": station.ward_floor if station else None,
	}


def _serialize(msg):
	return {
		"name": msg.name,
		"patient": msg.patient,
		"nursing_station": msg.nursing_station,
		"sender_type": msg.sender_type,
		"sender_name": msg.sender_name,
		"content": msg.content,
		"priority": msg.priority,
		"input_mode": msg.input_mode,
		"status": msg.status,
		"creation": frappe.utils.get_datetime_str(msg.creation),
		"read_at": frappe.utils.get_datetime_str(msg.read_at) if msg.read_at else None,
	}


# ── Nursing-station endpoints (staff login required) ──────────────────────────

@frappe.whitelist()
def get_station_patients(station):
	"""List active patients for a station. Any authenticated staff may call this."""
	_assert_staff(frappe.session.user)
	_assert_station(station)

	customers = frappe.get_all(
		"Customer",
		filters={"pc_nursing_center": station},
		fields=["name", "customer_name"],
		ignore_permissions=True,
	)

	result = []
	for c in customers:
		if not _get_active_allotment(c.name):
			continue
		payload = _build_patient_payload(c.name)
		last_msg = frappe.get_all(
			"Message",
			filters={"patient": c.name},
			fields=["content", "creation", "sender_type", "priority"],
			order_by="creation desc",
			limit=1,
			ignore_permissions=True,
		)
		payload["last_message"] = last_msg[0].content if last_msg else None
		payload["last_message_time"] = frappe.utils.get_datetime_str(last_msg[0].creation) if last_msg else None
		payload["has_urgent"] = bool(frappe.db.exists(
			"Message",
			{"patient": c.name, "priority": "Urgent", "sender_type": "Patient", "status": ["!=", "Read"]},
		))
		payload["unread_count"] = frappe.db.count(
			"Message", {"patient": c.name, "sender_type": "Patient", "status": ["!=", "Read"]}
		)
		result.append(payload)

	return sorted(result, key=lambda x: x.get("patient_name") or "")


@frappe.whitelist()
def get_messages(station, patient, after=None):
	"""Fetch conversation history for a patient (staff login required)."""
	_assert_staff(frappe.session.user)
	_assert_station(station)
	_assert_patient_in_station(patient, station)

	filters = {"patient": patient}
	if after:
		filters["creation"] = [">", after]

	return frappe.get_all(
		"Message",
		filters=filters,
		fields=[
			"name", "patient", "nursing_station", "sender_type", "sender_name",
			"content", "priority", "input_mode", "status", "creation", "read_at",
		],
		order_by="creation asc",
		ignore_permissions=True,
	)


def _assert_patient_in_station(patient, station):
	if not frappe.db.exists("Customer", {"name": patient, "pc_nursing_center": station}):
		frappe.throw(_("Patient does not belong to this station"), frappe.PermissionError)
	if not _get_active_allotment(patient):
		frappe.throw(_("Patient has no active admission"), frappe.PermissionError)


@frappe.whitelist()
def send_message(station, patient, content, input_mode="Text", priority="Normal"):
	"""Send a message from a staff member to a patient."""
	_assert_staff(frappe.session.user)
	_assert_station(station)
	_assert_patient_in_station(patient, station)

	content = (content or "").strip()
	if not content:
		frappe.throw(_("Message cannot be empty"))
	if priority not in ("Normal", "Urgent"):
		priority = "Normal"
	if input_mode not in ("Text", "Voice"):
		input_mode = "Text"

	station_doc = frappe.db.get_value(
		"Nursing Station", station, "nursing_station_name"
	)

	doc = frappe.get_doc({
		"doctype": "Message",
		"patient": patient,
		"nursing_station": station,
		"sender_type": "Nurse",
		"sender_name": station_doc or station,
		"content": content,
		"input_mode": input_mode,
		"priority": priority,
		"status": "Sent",
	})
	doc.insert(ignore_permissions=True)
	frappe.db.commit()

	payload = _serialize(doc)
	frappe.publish_realtime(event="pc_message", message=payload, user=frappe.session.user)
	return payload


@frappe.whitelist()
def mark_read(station, patient):
	"""Mark patient messages as Read (staff side)."""
	_assert_staff(frappe.session.user)
	_assert_patient_in_station(patient, station)

	unread = frappe.get_all(
		"Message",
		filters={"patient": patient, "sender_type": "Patient", "status": ["!=", "Read"]},
		pluck="name",
	)
	if not unread:
		return {"updated": 0}

	frappe.db.set_value(
		"Message", {"name": ["in", unread]}, {"status": "Read", "read_at": now_datetime()},
		update_modified=False,
	)
	frappe.db.commit()
	return {"updated": len(unread)}


@frappe.whitelist()
def send_typing(station, patient):
	"""Store nurse typing state in cache; patient polls get_typing_status_by_token for it."""
	_assert_staff(frappe.session.user)
	_assert_patient_in_station(patient, station)
	frappe.cache().set_value(f"pc_typing:{patient}", 1, expires_in_sec=4)
	return {"ok": 1}


@frappe.whitelist(allow_guest=True)
def get_typing_status_by_token(token=None):
	"""Return whether the nurse is currently typing (patient polls this)."""
	customer = _get_customer_for_token(token)
	if not customer:
		frappe.throw(_("Invalid or expired portal link"), frappe.PermissionError)
	return {"typing": bool(frappe.cache().get_value(f"pc_typing:{customer.name}"))}


# ── Token-based access (patient side — no login required) ─────────────────────

def _get_customer_for_token(token):
	if not token:
		return None
	name = frappe.db.get_value("Customer", {"pc_access_token": token}, "name")
	if not name:
		return None
	nc = frappe.db.get_value("Customer", name, "pc_nursing_center")
	if not nc:
		return None

	return frappe.get_doc("Customer", name)


@frappe.whitelist(allow_guest=True)
def get_my_patient_by_token(token=None):
	customer = _get_customer_for_token(token)
	if not customer:
		frappe.throw(_("Invalid or expired portal link"), frappe.PermissionError)
	return _build_patient_payload(customer.name)


@frappe.whitelist(allow_guest=True)
def get_messages_by_token(token=None, after=None):
	customer = _get_customer_for_token(token)
	if not customer:
		frappe.throw(_("Invalid or expired portal link"), frappe.PermissionError)

	filters = {"patient": customer.name}
	if after:
		filters["creation"] = [">", after]

	return frappe.get_all(
		"Message",
		filters=filters,
		fields=[
			"name", "patient", "nursing_station", "sender_type", "sender_name",
			"content", "priority", "input_mode", "status", "creation", "read_at",
		],
		order_by="creation asc",
		ignore_permissions=True,
	)


@frappe.whitelist(allow_guest=True)
def send_message_by_token(token=None, content=None, input_mode="Text", priority="Normal"):
	customer = _get_customer_for_token(token)
	if not customer:
		frappe.throw(_("Invalid or expired portal link"), frappe.PermissionError)

	content = (content or "").strip()
	if not content:
		frappe.throw(_("Message cannot be empty"))
	if priority not in ("Normal", "Urgent"):
		priority = "Normal"
	if input_mode not in ("Text", "Voice"):
		input_mode = "Text"

	nursing_station = customer.get("pc_nursing_center")
	doc = frappe.get_doc({
		"doctype": "Message",
		"patient": customer.name,
		"nursing_station": nursing_station,
		"sender_type": "Patient",
		"sender_name": customer.customer_name,
		"content": content,
		"input_mode": input_mode,
		"priority": priority,
		"status": "Sent",
	})
	doc.insert(ignore_permissions=True)
	frappe.db.commit()

	payload = _serialize(doc)
	# Broadcast to all logged-in users so nurses receive new patient messages in realtime
	frappe.publish_realtime(event="pc_message", message=payload)
	return payload


@frappe.whitelist(allow_guest=True)
def mark_read_by_token(token=None):
	customer = _get_customer_for_token(token)
	if not customer:
		frappe.throw(_("Invalid or expired portal link"), frappe.PermissionError)

	unread = frappe.get_all(
		"Message",
		filters={"patient": customer.name, "sender_type": "Nurse", "status": ["!=", "Read"]},
		pluck="name",
	)
	if not unread:
		return {"updated": 0}

	frappe.db.set_value(
		"Message", {"name": ["in", unread]}, {"status": "Read", "read_at": now_datetime()},
		update_modified=False,
	)
	frappe.db.commit()
	return {"updated": len(unread)}


@frappe.whitelist(allow_guest=True)
def send_typing_by_token(token=None):
	customer = _get_customer_for_token(token)
	if not customer:
		frappe.throw(_("Invalid or expired portal link"), frappe.PermissionError)
	frappe.publish_realtime(
		event="pc_typing",
		message={"patient": customer.name, "sender_name": customer.customer_name},
	)
	return {"ok": 1}


# ── Nursing-center assignment ─────────────────────────────────────────────────

@frappe.whitelist()
def assign_nursing_center(customer, nursing_center):
	"""Assign (or clear) a nursing center on a Customer and return the portal link."""
	_assert_staff(frappe.session.user)

	if not frappe.db.exists("Customer", customer):
		frappe.throw(_("Customer not found"), frappe.DoesNotExistError)

	nursing_center = (nursing_center or "").strip() or None

	if nursing_center and not frappe.db.exists("Nursing Station", {"name": nursing_center, "is_active": 1}):
		frappe.throw(_("Nursing station not found or inactive"), frappe.ValidationError)

	if not _get_active_allotment(customer):
		frappe.throw(_("Patient has no active admission"), frappe.ValidationError)

	_dfr = _device_field_ready()

	update = {"pc_nursing_center": nursing_center}
	if not nursing_center:
		update["pc_access_token"] = None
		if _dfr:
			update["pc_device_id"] = None

	frappe.db.set_value("Customer", customer, update)

	if not nursing_center:
		frappe.db.commit()
		return {"assigned": False}

	token = frappe.db.get_value("Customer", customer, "pc_access_token")
	if not token:
		token = random_string(32)
		frappe.db.set_value("Customer", customer, "pc_access_token", token)

	# Reset device binding so the patient can bind on whichever device receives the new link
	if _dfr:
		frappe.db.set_value("Customer", customer, "pc_device_id", None, update_modified=False)

	frappe.db.commit()

	site_url = frappe.utils.get_url().rstrip("/")
	portal_url = f"{site_url}/patient?token={token}"

	try:
		customer_data = frappe.db.get_value("Customer", customer, ["mobile_no", "pw_phone"], as_dict=True) or frappe._dict()
		phone = (customer_data.get("mobile_no") or customer_data.get("pw_phone") or "").strip()
	except Exception:
		phone = (frappe.db.get_value("Customer", customer, "mobile_no") or "").strip()
	phone_clean = "".join(c for c in phone if c.isdigit() or c == "+").lstrip("+")

	import urllib.parse
	wa_message = f"Your patient communication portal link: {portal_url}"
	whatsapp_url = f"https://wa.me/{phone_clean}?text={urllib.parse.quote(wa_message)}" if phone_clean else None

	return {
		"assigned": True,
		"portal_url": portal_url,
		"whatsapp_url": whatsapp_url,
	}


# ── PWA manifest (served from a real URL so Chrome fires beforeinstallprompt) ──

@frappe.whitelist(allow_guest=True)
def get_pwa_manifest(token):
	if not token:
		frappe.throw("", frappe.PermissionError)
	name = frappe.db.get_value("Customer", {"pc_access_token": token}, "name")
	if not name:
		frappe.throw("", frappe.PermissionError)
	try:
		title = frappe.db.get_single_value("Website Settings", "title") or "Patient Portal"
	except Exception:
		title = "Patient Portal"
	manifest = {
		"name": title,
		"short_name": title,
		"description": "Communicate with your nursing station",
		"start_url": "/patient?token=" + token,
		"display": "standalone",
		"orientation": "portrait",
		"background_color": "#f8fafc",
		"theme_color": "#3d5a99",
		"icons": [
			{
				"src": "/assets/patient_communications/images/pc-icon.svg",
				"sizes": "192x192 512x512",
				"type": "image/svg+xml",
				"purpose": "any maskable",
			}
		],
	}
	# Spread manifest fields into the response root so Chrome receives them
	# directly (not wrapped under "message").  Returning None prevents Frappe
	# from adding a "message" key.
	frappe.local.response.update(manifest)


# ── Device claim (called by patient browser JS) ───────────────────────────────

@frappe.whitelist(allow_guest=True)
def claim_device_token(token):
	"""Validate a patient portal token.

	Called by JavaScript on page load.  Link-preview bots (WhatsApp, Telegram,
	iMessage…) never run JS so they cannot trigger this call.

	Returns:
	  {"status": "ok"}      — valid token with a nursing center assigned
	  {"status": "invalid"} — bad or expired token
	"""
	if not token:
		return {"status": "invalid"}

	name = frappe.db.get_value("Customer", {"pc_access_token": token}, "name")
	if not name:
		return {"status": "invalid"}

	nc = frappe.db.get_value("Customer", name, "pc_nursing_center")
	if not nc:
		return {"status": "invalid"}

	return {"status": "ok"}


# ── Portal link generation ────────────────────────────────────────────────────

@frappe.whitelist()
def get_communication_link(customer):
	nc = frappe.db.get_value("Customer", customer, "pc_nursing_center")
	if not nc or not _get_active_allotment(customer):
		frappe.throw(
			_("Cannot generate link: ensure the customer has an active IPD allotment and a Nursing Center assigned."),
			frappe.ValidationError,
		)

	token = frappe.db.get_value("Customer", customer, "pc_access_token")
	if not token:
		token = random_string(32)
		frappe.db.set_value("Customer", customer, "pc_access_token", token)

	# Reset device binding so the link can be opened on any device
	if _device_field_ready():
		frappe.db.set_value("Customer", customer, "pc_device_id", None, update_modified=False)

	frappe.db.commit()

	site_url = frappe.utils.get_url().rstrip("/")
	portal_url = f"{site_url}/patient?token={token}"

	try:
		customer_data = frappe.db.get_value("Customer", customer, ["mobile_no", "pw_phone"], as_dict=True) or frappe._dict()
		phone = (customer_data.get("mobile_no") or customer_data.get("pw_phone") or "").strip()
	except Exception:
		phone = (frappe.db.get_value("Customer", customer, "mobile_no") or "").strip()
	phone_clean = "".join(c for c in phone if c.isdigit() or c == "+").lstrip("+")

	import urllib.parse
	wa_message = f"Your patient communication portal link: {portal_url}"
	whatsapp_url = f"https://wa.me/{phone_clean}?text={urllib.parse.quote(wa_message)}" if phone_clean else None

	return {
		"portal_url": portal_url,
		"whatsapp_url": whatsapp_url,
		"phone": phone,
		"token": token,
	}

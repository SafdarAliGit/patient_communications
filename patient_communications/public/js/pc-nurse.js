frappe.ready(function () {
	const appEl = document.getElementById("pc-app");
	const stationName = appEl ? appEl.dataset.station : "";

	const $sidebar = document.getElementById("pc-sidebar");
	const $list = document.getElementById("pc-patient-list");
	const $search = document.getElementById("pc-search");
	const $threadWrap = document.getElementById("pc-thread-wrap");
	const $thread = document.getElementById("pc-thread");
	const $input = document.getElementById("pc-input");
	const $sendBtn = document.getElementById("pc-send-btn");
	const $micBtn = document.getElementById("pc-mic-btn");
	const $backBtn = document.getElementById("pc-back-btn");
	const $activeName = document.getElementById("pc-active-patient-name");
	const $activeSub = document.getElementById("pc-active-patient-sub");
	const $statusEl = document.getElementById("pc-status");
	const $statusText = document.getElementById("pc-status-text");
	const $patientCount = document.getElementById("pc-patient-count");

	let patients = [];
	let activePatient = null;
	let lastRenderedDay = null;
	let typingTimeout = null;
	let typingEl = null;

	function setStatus(online) {
		$statusEl.classList.toggle("is-online", online);
		$statusEl.classList.toggle("is-offline", !online);
		$statusText.textContent = online ? "Connected" : "Reconnecting…";
	}

	function initials(name) {
		return (name || "")
			.split(" ")
			.filter(Boolean)
			.slice(0, 2)
			.map((s) => s[0].toUpperCase())
			.join("");
	}

	function renderList() {
		const q = ($search.value || "").toLowerCase().trim();
		const filtered = patients.filter((p) => {
			if (!q) return true;
			return (
				(p.patient_name || "").toLowerCase().includes(q) ||
				(p.room_no || "").toLowerCase().includes(q) ||
				(p.bed_no || "").toLowerCase().includes(q) ||
				(p.mr_no || "").toLowerCase().includes(q)
			);
		});

		filtered.sort((a, b) => {
			if (a.has_urgent !== b.has_urgent) return a.has_urgent ? -1 : 1;
			return (b.last_message_time || "").localeCompare(a.last_message_time || "");
		});

		$list.innerHTML = "";
		if (!filtered.length) {
			$list.innerHTML =
				'<div class="pc-empty"><svg width="34" height="34" viewBox="0 0 24 24" fill="none">' +
				'<circle cx="9" cy="8" r="3.2" stroke="currentColor" stroke-width="1.6"/>' +
				'<path d="M3.5 19c.6-3.2 3-5 5.5-5s4.9 1.8 5.5 5M16 8.5a2.8 2.8 0 1 0 0-5.6M20.5 19c-.4-2.2-1.6-3.8-3.3-4.6" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>' +
				"</svg>No patients found.</div>";
			return;
		}

		filtered.forEach((p) => {
			const item = document.createElement("div");
			item.className =
				"pc-patient-item" +
				(p.name === activePatient ? " is-active" : "") +
				(p.has_urgent ? " is-urgent" : "");
			item.dataset.name = p.name;

			const locationParts = [];
			if (p.floor_no) locationParts.push("Floor " + p.floor_no);
			if (p.room_no) locationParts.push("Room " + p.room_no);
			if (p.bed_no) locationParts.push("Bed " + p.bed_no);
			const locationLabel = locationParts.join(" · ");

			item.innerHTML =
				'<div class="pc-avatar" style="background:' + PC.avatarColor(p.name) + '">' +
				PC.escapeHtml(initials(p.patient_name)) + "</div>" +
				'<div class="pc-patient-meta">' +
				'<div class="pc-row1"><span class="pc-pname">' + PC.escapeHtml(p.patient_name) + "</span>" +
				'<span class="pc-time">' + (p.last_message_time ? PC.formatTime(p.last_message_time) : "") + "</span></div>" +
				'<div class="pc-row-loc">' +
				(p.mr_no ? '<span class="pc-mr">MR&nbsp;' + PC.escapeHtml(p.mr_no) + "</span>" : "") +
				(p.mr_no && locationLabel ? '<span class="pc-loc-dot">&middot;</span>' : "") +
				(locationLabel ? '<span class="pc-loc">' + PC.escapeHtml(locationLabel) + "</span>" : "") +
				"</div>" +
				'<div class="pc-row2"><span class="pc-preview">' +
				PC.escapeHtml(p.last_message || "No messages yet") +
				"</span>" +
				(p.unread_count ? '<span class="pc-badge' + (p.has_urgent ? " is-urgent" : "") + '">' + p.unread_count + "</span>" : "") +
				"</div></div>";

			item.addEventListener("click", () => selectPatient(p.name));
			$list.appendChild(item);
		});
	}

	async function loadPatients() {
		patients = await PC.call("patient_communications.api.get_station_patients", { station: stationName });
		if ($patientCount) $patientCount.textContent = patients.length || "";
		renderList();
	}

	function scrollToBottom() {
		$thread.scrollTop = $thread.scrollHeight;
	}

	function renderMessage(msg) {
		const isOut = msg.sender_type === "Nurse";
		const day = PC.formatDay(msg.creation);
		if (day !== lastRenderedDay) {
			const sep = document.createElement("div");
			sep.className = "pc-day-sep";
			sep.textContent = day;
			$thread.appendChild(sep);
			lastRenderedDay = day;
		}

		const row = document.createElement("div");
		row.className = "pc-bubble-row " + (isOut ? "is-out" : "is-in") + (msg.priority === "Urgent" ? " is-urgent" : "");
		row.dataset.name = msg.name;

		const bubble = document.createElement("div");
		bubble.className = "pc-bubble";
		bubble.innerHTML = PC.escapeHtml(msg.content);

		const meta = document.createElement("div");
		meta.className = "pc-bubble-meta";
		let metaHtml = PC.formatTime(msg.creation);
		if (msg.input_mode === "Voice") {
			metaHtml += ' &middot; <span class="pc-voice-tag">🎤 voice</span>';
		}
		if (isOut) {
			metaHtml += msg.status === "Read" ? " &middot; Read" : msg.status === "Delivered" ? " &middot; Delivered" : " &middot; Sent";
		}
		meta.innerHTML = metaHtml;

		bubble.appendChild(meta);
		row.appendChild(bubble);
		$thread.appendChild(row);
	}

	function showTyping(show) {
		if (show) {
			if (typingEl) return;
			typingEl = document.createElement("div");
			typingEl.className = "pc-typing";
			typingEl.innerHTML = "<span></span><span></span><span></span>";
			$thread.appendChild(typingEl);
			scrollToBottom();
		} else if (typingEl) {
			typingEl.remove();
			typingEl = null;
		}
	}

	async function selectPatient(name) {
		activePatient = name;
		const p = patients.find((x) => x.name === name);
		$activeName.textContent = p ? p.patient_name : "";
		const roomBed = p ? [p.room_no, p.bed_no].filter(Boolean).join(" / ") : "";
		$activeSub.textContent = roomBed || "";

		$input.disabled = false;
		$sendBtn.disabled = false;

		if (window.innerWidth <= 860) {
			$sidebar.classList.add("is-hidden");
		}
		$threadWrap.classList.remove("is-hidden");

		$thread.innerHTML = "";
		lastRenderedDay = null;
		const messages = await PC.call("patient_communications.api.get_messages", { station: stationName, patient: name });
		messages.forEach(renderMessage);
		scrollToBottom();
		await PC.call("patient_communications.api.mark_read", { station: stationName, patient: name });
		loadPatients();
		renderList();
	}

	$backBtn.addEventListener("click", () => {
		$sidebar.classList.remove("is-hidden");
		if (window.innerWidth <= 860) {
			$threadWrap.classList.add("is-hidden");
		}
	});

	$search.addEventListener("input", renderList);

	async function sendMessage(content, inputMode) {
		content = (content || "").trim();
		if (!content || !activePatient) return;
		try {
			await PC.call("patient_communications.api.send_message", {
				station: stationName,
				patient: activePatient,
				content: content,
				input_mode: inputMode || "Text",
				priority: "Normal",
			});
			$input.value = "";
			$input.dataset.viaVoice = "";
			$input.dataset.baseValue = "";
			autoResize();
		} catch (e) {
			PC.toast("Message failed to send.", { urgent: true });
		}
	}

	function autoResize() {
		$input.style.height = "auto";
		$input.style.height = Math.min($input.scrollHeight, 120) + "px";
	}

	function sendFromComposer() {
		const mode = $input.dataset.viaVoice === "1" ? "Voice" : "Text";
		sendMessage($input.value, mode);
	}

	$sendBtn.addEventListener("click", sendFromComposer);
	$input.addEventListener("input", () => {
		autoResize();
		if (!activePatient) return;
		if (typingTimeout) clearTimeout(typingTimeout);
		typingTimeout = setTimeout(() => {
			PC.call("patient_communications.api.send_typing", { station: stationName, patient: activePatient });
		}, 400);
	});
	$input.addEventListener("keydown", (e) => {
		if (e.key === "Enter" && !e.shiftKey) {
			e.preventDefault();
			sendFromComposer();
			return;
		}
		$input.dataset.viaVoice = "";
	});

	// ---- Voice to text ----
	const voice = new PC.VoiceInput({
		lang: "en-US",
		onStart: () => $micBtn.classList.add("is-recording"),
		onEnd: () => $micBtn.classList.remove("is-recording"),
		onInterim: (text) => {
			$input.value = ($input.dataset.baseValue || "") + text;
			autoResize();
		},
		onFinal: (text) => {
			$input.dataset.baseValue = ($input.dataset.baseValue || "") + text;
			$input.value = $input.dataset.baseValue;
			$input.dataset.viaVoice = "1";
			autoResize();
		},
		onError: (err) => {
			if (err !== "no-speech" && err !== "aborted") {
				PC.toast("Voice input error: " + err);
			}
		},
	});

	if (voice.supported) {
		$micBtn.style.display = "";
		$micBtn.addEventListener("click", () => {
			if (voice.listening) {
				voice.stop();
			} else {
				$input.dataset.baseValue = $input.value ? $input.value.replace(/\n+$/, "") + "\n" : "";
				voice.start();
			}
		});
	}

	// ---- Realtime ----
	PC.initRealtime();

	frappe.realtime.on("pc_message", (msg) => {
		if (msg.patient === activePatient) {
			showTyping(false);
			renderMessage(msg);
			scrollToBottom();
			if (msg.sender_type === "Patient") {
				PC.call("patient_communications.api.mark_read", { station: stationName, patient: activePatient });
			}
		}
		if (msg.sender_type === "Patient") {
			PC.notifySound();
			PC.browserNotify(
				(msg.priority === "Urgent" ? "URGENT — " : "") + (msg.sender_name || "Patient"),
				msg.content
			);
			if (msg.priority === "Urgent") {
				PC.toast("Urgent message from " + (msg.sender_name || "a patient"), { urgent: true });
			}
		}
		loadPatients();
	});

	frappe.realtime.on("pc_typing", (data) => {
		if (data.patient !== activePatient) return;
		showTyping(true);
		setTimeout(() => showTyping(false), 3000);
	});

	frappe.realtime.on("pc_message_read", (data) => {
		if (data.patient !== activePatient) return;
		(data.message_names || []).forEach((name) => {
			const row = $thread.querySelector('[data-name="' + name + '"] .pc-bubble-meta');
			if (row) row.innerHTML = row.innerHTML.replace(/(Sent|Delivered)$/, "Read");
		});
	});

	setTimeout(() => {
		if (frappe.realtime.socket) {
			setStatus(frappe.realtime.socket.connected);
			frappe.realtime.socket.on("connect", () => setStatus(true));
			frappe.realtime.socket.on("disconnect", () => setStatus(false));
		}
	}, 300);

	PC.requestNotificationPermission();
	loadPatients();
});

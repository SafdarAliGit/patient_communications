frappe.ready(function () {
	const appEl = document.getElementById("pc-app");
	const patientName = appEl.dataset.patient;
	const accessToken = appEl.dataset.token || "";
	const tokenMode = !!accessToken;  // true = link-based (no Frappe login)
	const $thread = document.getElementById("pc-thread");
	const $input = document.getElementById("pc-input");
	const $sendBtn = document.getElementById("pc-send-btn");
	const $micBtn = document.getElementById("pc-mic-btn");
	const $urgentBtn = document.getElementById("pc-urgent-btn");
	const $statusEl = document.getElementById("pc-status");
	const $statusText = document.getElementById("pc-status-text");
	const $stationName = document.getElementById("pc-station-name");

	let lastRenderedDay = null;
	let typingTimeout = null;
	let typingEl = null;
	let lastMessageTime = null;  // for polling in token mode
	let pollInterval = null;
	let typingPollInterval = null;

	function setStatus(online) {
		$statusEl.classList.toggle("is-online", online);
		$statusEl.classList.toggle("is-offline", !online);
		$statusText.textContent = online ? "Connected" : "Reconnecting…";
	}

	function scrollToBottom() {
		$thread.scrollTop = $thread.scrollHeight;
	}

	function renderMessage(msg) {
		const isOut = msg.sender_type === "Patient";
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

	async function loadHistory() {
		const method = tokenMode
			? "patient_communications.api.get_messages_by_token"
			: "patient_communications.api.get_messages";
		const args = tokenMode ? { token: accessToken } : {};
		const messages = await PC.call(method, args);
		$thread.innerHTML = "";
		lastRenderedDay = null;
		messages.forEach(renderMessage);
		if (messages.length) lastMessageTime = messages[messages.length - 1].creation;
		scrollToBottom();
		const markMethod = tokenMode
			? "patient_communications.api.mark_read_by_token"
			: "patient_communications.api.mark_read";
		PC.call(markMethod, tokenMode ? { token: accessToken } : {});
	}

	async function pollNewMessages() {
		// Only used in token mode (no realtime for guest sessions)
		if (!tokenMode) return;
		const args = { token: accessToken };
		if (lastMessageTime) args.after = lastMessageTime;
		try {
			const msgs = await PC.call("patient_communications.api.get_messages_by_token", args);
			if (msgs && msgs.length) {
				msgs.forEach((msg) => {
					renderMessage(msg);
					if (msg.sender_type === "Nurse") {
						PC.notifySound();
						PC.browserNotify(msg.sender_name || "Nursing Station", msg.content);
					}
				});
				lastMessageTime = msgs[msgs.length - 1].creation;
				scrollToBottom();
				PC.call("patient_communications.api.mark_read_by_token", { token: accessToken });
			}
		} catch (e) { /* ignore poll errors */ }
	}

	async function loadIdentity() {
		try {
			const method = tokenMode
				? "patient_communications.api.get_my_patient_by_token"
				: "patient_communications.api.get_my_patient";
			const args = tokenMode ? { token: accessToken } : {};
			const info = await PC.call(method, args);
			$stationName.textContent = info.station_name || "Nursing Station";
		} catch (e) {
			$stationName.textContent = "Nursing Station";
		}
	}

	async function sendMessage(content, inputMode, priority) {
		content = (content || "").trim();
		if (!content) return;
		try {
			if (tokenMode) {
				const msg = await PC.call("patient_communications.api.send_message_by_token", {
					token: accessToken,
					content: content,
					input_mode: inputMode || "Text",
					priority: priority || "Normal",
				});
				renderMessage(msg);
				lastMessageTime = msg.creation;
				scrollToBottom();
			} else {
				await PC.call("patient_communications.api.send_message", {
					content: content,
					input_mode: inputMode || "Text",
					priority: priority || "Normal",
				});
			}
			$input.value = "";
			autoResize();
		} catch (e) {
			PC.toast("Message failed to send. Check your connection.", { urgent: true });
		}
	}

	function autoResize() {
		$input.style.height = "auto";
		$input.style.height = Math.min($input.scrollHeight, 120) + "px";
	}

	// ---- Composer wiring ----
	function sendFromComposer() {
		const mode = $input.dataset.viaVoice === "1" ? "Voice" : "Text";
		sendMessage($input.value, mode, "Normal");
		$input.dataset.viaVoice = "";
		$input.dataset.baseValue = "";
	}

	$sendBtn.addEventListener("click", sendFromComposer);
	$input.addEventListener("input", () => {
		autoResize();
		if (typingTimeout) clearTimeout(typingTimeout);
		typingTimeout = setTimeout(() => {
			if (tokenMode) {
				PC.call("patient_communications.api.send_typing_by_token", { token: accessToken });
			} else {
				PC.call("patient_communications.api.send_typing", {});
			}
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

	$urgentBtn.addEventListener("click", () => {
		sendMessage("I need urgent assistance, please attend to me now.", "Text", "Urgent");
		PC.toast("Urgent request sent to your nursing station.", { urgent: true });
	});

	// ---- Voice to text ----
	const voice = new PC.VoiceInput({
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

	async function pollTypingStatus() {
		try {
			const res = await PC.call("patient_communications.api.get_typing_status_by_token", { token: accessToken });
			showTyping(res && res.typing);
		} catch (e) { /* ignore */ }
	}

	// ---- Realtime (session mode only) / Polling (token mode) ----
	if (tokenMode) {
		// No Frappe session in link-based mode — poll for messages and typing state
		setStatus(true);
		pollInterval = setInterval(pollNewMessages, 3000);
		typingPollInterval = setInterval(pollTypingStatus, 1500);
	} else {
		PC.initRealtime();
		frappe.realtime.on("pc_message", (msg) => {
			if (msg.patient !== patientName) return;
			showTyping(false);
			renderMessage(msg);
			scrollToBottom();
			if (msg.sender_type === "Nurse") {
				PC.notifySound();
				PC.browserNotify(msg.sender_name || "Nursing Station", msg.content);
				PC.call("patient_communications.api.mark_read", {});
			}
		});

		frappe.realtime.on("pc_typing", (data) => {
			if (data.patient !== patientName) return;
			showTyping(true);
			setTimeout(() => showTyping(false), 3000);
		});

		frappe.realtime.on("pc_message_read", (data) => {
			if (data.patient !== patientName) return;
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
	}

	PC.requestNotificationPermission();
	loadIdentity();
	loadHistory();
});

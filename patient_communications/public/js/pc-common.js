// Patient Communications — shared client helpers
window.PC = window.PC || {};

PC.call = function (method, args) {
	return new Promise((resolve, reject) => {
		frappe.call({
			method: method,
			args: args || {},
			callback: (r) => resolve(r.message),
			error: (r) => reject(r),
		});
	});
};

PC.initRealtime = function () {
	// frappe.boot.socketio_port only exists in desk boot info; website pages only get
	// the plain global `window.socketio_port` (set in templates/base.html).
	frappe.realtime.init(window.socketio_port || (frappe.boot && frappe.boot.socketio_port));
};

PC.toast = function (text, opts) {
	opts = opts || {};
	let wrap = document.querySelector(".pc-toast-wrap");
	if (!wrap) {
		wrap = document.createElement("div");
		wrap.className = "pc-toast-wrap";
		document.body.appendChild(wrap);
	}
	const el = document.createElement("div");
	el.className = "pc-toast" + (opts.urgent ? " is-urgent" : "");
	el.textContent = text;
	wrap.appendChild(el);
	setTimeout(() => el.remove(), opts.duration || 4500);
};

PC.escapeHtml = function (str) {
	const div = document.createElement("div");
	div.textContent = str == null ? "" : String(str);
	return div.innerHTML;
};

PC.formatTime = function (dtStr) {
	if (!dtStr) return "";
	const d = new Date(dtStr.replace(" ", "T"));
	if (isNaN(d.getTime())) return "";
	return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
};

PC.avatarColor = function (seed) {
	const palette = [
		"--pc-avatar-1",
		"--pc-avatar-2",
		"--pc-avatar-3",
		"--pc-avatar-4",
		"--pc-avatar-5",
		"--pc-avatar-6",
	];
	let hash = 0;
	const str = seed || "";
	for (let i = 0; i < str.length; i++) {
		hash = (hash * 31 + str.charCodeAt(i)) >>> 0;
	}
	return `var(${palette[hash % palette.length]})`;
};

PC.formatDay = function (dtStr) {
	const d = new Date(dtStr.replace(" ", "T"));
	if (isNaN(d.getTime())) return "";
	const today = new Date();
	const isToday = d.toDateString() === today.toDateString();
	const yesterday = new Date(today);
	yesterday.setDate(yesterday.getDate() - 1);
	if (isToday) return "Today";
	if (d.toDateString() === yesterday.toDateString()) return "Yesterday";
	return d.toLocaleDateString([], { month: "short", day: "numeric", year: "numeric" });
};

PC.notifySound = function () {
	try {
		const ctx = new (window.AudioContext || window.webkitAudioContext)();
		const o = ctx.createOscillator();
		const g = ctx.createGain();
		o.connect(g);
		g.connect(ctx.destination);
		o.type = "sine";
		o.frequency.setValueAtTime(880, ctx.currentTime);
		g.gain.setValueAtTime(0.15, ctx.currentTime);
		g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.4);
		o.start();
		o.stop(ctx.currentTime + 0.4);
	} catch (e) {
		/* audio not available */
	}
};

PC.requestNotificationPermission = function () {
	if ("Notification" in window && Notification.permission === "default") {
		Notification.requestPermission();
	}
};

PC.browserNotify = function (title, body) {
	if ("Notification" in window && Notification.permission === "granted" && document.hidden) {
		try {
			new Notification(title, { body: body, tag: "pc-message" });
		} catch (e) {
			/* ignore */
		}
	}
};

/**
 * Thin wrapper around the browser's native Web Speech API.
 * Feature-detects and no-ops cleanly where unsupported (Firefox, most non-Chromium browsers).
 */
PC.VoiceInput = function (opts) {
	const SpeechRecognitionImpl = window.SpeechRecognition || window.webkitSpeechRecognition;
	this.supported = !!SpeechRecognitionImpl;
	this.onInterim = opts.onInterim || function () {};
	this.onFinal = opts.onFinal || function () {};
	this.onStart = opts.onStart || function () {};
	this.onEnd = opts.onEnd || function () {};
	this.onError = opts.onError || function () {};
	this.listening = false;

	if (!this.supported) return;

	this.recognition = new SpeechRecognitionImpl();
	this.recognition.continuous = false;
	this.recognition.interimResults = true;
	this.recognition.lang = opts.lang || "en-US";

	const self = this;

	this.recognition.onstart = function () {
		self.listening = true;
		self.onStart();
	};

	this.recognition.onresult = function (event) {
		let interim = "";
		let final = "";
		for (let i = event.resultIndex; i < event.results.length; i++) {
			const transcript = event.results[i][0].transcript;
			if (event.results[i].isFinal) {
				final += transcript;
			} else {
				interim += transcript;
			}
		}
		if (interim) self.onInterim(interim);
		if (final) self.onFinal(final);
	};

	this.recognition.onerror = function (event) {
		self.onError(event.error);
	};

	this.recognition.onend = function () {
		self.listening = false;
		self.onEnd();
	};
};

PC.VoiceInput.prototype.start = function () {
	if (!this.supported || this.listening) return;
	try {
		this.recognition.start();
	} catch (e) {
		/* already started */
	}
};

PC.VoiceInput.prototype.stop = function () {
	if (!this.supported) return;
	try {
		this.recognition.stop();
	} catch (e) {
		/* ignore */
	}
};

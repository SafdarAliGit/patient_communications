// patient_communications — adds "Send Patient Comms Link" button to Customer form
frappe.ui.form.on("Customer", {
	refresh(frm) {
		if (frm.is_new() || !frm.doc.pc_nursing_center) return;

		frm.add_custom_button(__("Send Patient Comms Link"), function () {
			frappe.call({
				method: "patient_communications.api.get_communication_link",
				args: { customer: frm.doc.name },
				freeze: true,
				freeze_message: __("Generating link…"),
				callback(r) {
					if (r.exc) return;
					_show_link_dialog(r.message);
				},
			});
		}, __("Patient Communications"));
	},
});

function _show_link_dialog(d) {
	const waBtn = d.whatsapp_url
		? `<a href="${frappe.utils.escape_html(d.whatsapp_url)}" target="_blank" rel="noopener"
				class="btn btn-success btn-sm" style="width:100%;text-align:center;margin-top:8px;">
				<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"
					style="vertical-align:middle;margin-right:6px;">
					<path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347z"/>
					<path d="M12 0C5.373 0 0 5.373 0 12c0 2.136.564 4.14 1.546 5.878L0 24l6.335-1.521A11.944 11.944 0 0012 24c6.627 0 12-5.373 12-12S18.627 0 12 0zm0 21.818a9.798 9.798 0 01-5.031-1.389l-.361-.214-3.761.903.945-3.655-.235-.374A9.798 9.798 0 012.182 12C2.182 6.57 6.57 2.182 12 2.182S21.818 6.57 21.818 12 17.43 21.818 12 21.818z"/>
				</svg>
				${__("Send via WhatsApp")}
			</a>`
		: `<p style="color:#6b7280;font-size:12px;margin-top:8px;">${__("No phone number on record — copy the link above and share manually.")}</p>`;

	const dialog = new frappe.ui.Dialog({
		title: __("Patient Communication Link"),
		fields: [
			{
				fieldtype: "HTML",
				options: `
				<div style="margin-bottom:4px;">
					<label style="font-size:11px;font-weight:600;color:#6b7280;text-transform:uppercase;letter-spacing:.04em;">
						Portal Link
					</label>
					<div style="display:flex;align-items:center;gap:8px;margin-top:6px;">
						<input id="pc-link-input" type="text"
							value="${frappe.utils.escape_html(d.portal_url)}"
							readonly
							style="flex:1;padding:7px 10px;border:1px solid #d1d5db;border-radius:6px;font-size:13px;background:#f9fafb;">
						<button id="pc-copy-btn" class="btn btn-default btn-sm">${__("Copy")}</button>
					</div>
				</div>
				${waBtn}`,
			},
		],
		primary_action_label: __("Done"),
		primary_action() { dialog.hide(); },
	});

	dialog.show();

	dialog.$wrapper.find("#pc-copy-btn").on("click", function () {
		const input = dialog.$wrapper.find("#pc-link-input")[0];
		input.select();
		document.execCommand("copy");
		frappe.show_alert({ message: __("Link copied!"), indicator: "green" }, 2);
	});
}

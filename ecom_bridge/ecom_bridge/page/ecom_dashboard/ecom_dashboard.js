frappe.pages["ecom-dashboard"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Ecom Bridge Dashboard",
		single_column: true,
	});

	page.set_primary_action(__("Refresh"), () => load_dashboard(page), "refresh");

	page.set_secondary_action(__("Force Sync Shopify"), () => {
		frappe.call({
			method: "ecom_bridge.api.dashboard.force_sync",
			args: { integration: "shopify" },
			callback: (r) => {
				frappe.show_alert({ message: r.message.message, indicator: "green" });
			},
		});
	});

	page.add_inner_button(__("Force Sync Amazon"), () => {
		frappe.call({
			method: "ecom_bridge.api.dashboard.force_sync",
			args: { integration: "amazon" },
			callback: (r) => {
				frappe.show_alert({ message: r.message.message, indicator: "green" });
			},
		});
	});

	page.add_inner_button(__("Settings"), () => {
		frappe.set_route("Form", "Ecom Bridge Settings");
	});

	load_dashboard(page);
};

function load_dashboard(page) {
	page.main.html('<div class="ecom-dashboard-loading text-center" style="padding: 60px;"><div class="spinner-border" role="status"></div></div>');

	frappe.call({
		method: "ecom_bridge.api.dashboard.get_sync_dashboard",
		callback: (r) => {
			if (r.message) {
				render_dashboard(page, r.message);
			}
		},
	});
}

function render_dashboard(page, data) {
	const shopify = data.shopify || {};
	const amazon = data.amazon || {};
	const summary = data.summary || {};
	const errors = data.recent_errors || [];

	const last_sync = summary.last_sync
		? frappe.datetime.prettyDate(summary.last_sync)
		: "Never";

	let html = `
		<div class="ecom-dashboard" style="padding: 15px;">
			<!-- Summary Row -->
			<div class="row" style="margin-bottom: 20px;">
				<div class="col-md-4">
					<div class="card" style="padding: 20px; text-align: center; border-left: 4px solid var(--primary);">
						<h1 style="margin: 0; font-size: 36px;">${summary.total_orders_today || 0}</h1>
						<p style="margin: 5px 0 0; color: var(--text-muted);">${__("Orders Today")}</p>
					</div>
				</div>
				<div class="col-md-4">
					<div class="card" style="padding: 20px; text-align: center; border-left: 4px solid ${summary.total_errors_today > 0 ? 'var(--red)' : 'var(--green)'};">
						<h1 style="margin: 0; font-size: 36px; color: ${summary.total_errors_today > 0 ? 'var(--red)' : 'inherit'};">${summary.total_errors_today || 0}</h1>
						<p style="margin: 5px 0 0; color: var(--text-muted);">${__("Errors Today")}</p>
					</div>
				</div>
				<div class="col-md-4">
					<div class="card" style="padding: 20px; text-align: center; border-left: 4px solid var(--text-muted);">
						<h6 style="margin: 0;">${last_sync}</h6>
						<p style="margin: 5px 0 0; color: var(--text-muted);">${__("Last Sync")}</p>
					</div>
				</div>
			</div>

			<!-- Platform Cards -->
			<div class="row" style="margin-bottom: 20px;">
				<!-- Shopify -->
				<div class="col-md-6">
					<div class="card" style="padding: 20px;">
						<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
							<h5 style="margin: 0;">${__("Shopify")}</h5>
							<span class="indicator-pill ${shopify.enabled ? 'green' : 'red'}">
								${shopify.enabled ? __("Connected") : __("Disabled")}
							</span>
						</div>
						<div class="row">
							<div class="col-6">
								<div style="margin-bottom: 10px;">
									<span style="font-size: 24px; font-weight: bold;">${shopify.orders_today || 0}</span>
									<br><small class="text-muted">${__("Orders Today")}</small>
								</div>
							</div>
							<div class="col-6">
								<div style="margin-bottom: 10px;">
									<span style="font-size: 24px; font-weight: bold;">${shopify.orders_this_week || 0}</span>
									<br><small class="text-muted">${__("This Week")}</small>
								</div>
							</div>
							<div class="col-6">
								<div>
									<span style="font-size: 24px; font-weight: bold;">${shopify.total_products_synced || 0}</span>
									<br><small class="text-muted">${__("Products Synced")}</small>
								</div>
							</div>
							<div class="col-6">
								<div>
									<span style="font-size: 24px; font-weight: bold; color: ${shopify.errors_today > 0 ? 'var(--red)' : 'inherit'};">${shopify.errors_today || 0}</span>
									<br><small class="text-muted">${__("Errors Today")}</small>
								</div>
							</div>
						</div>
					</div>
				</div>

				<!-- Amazon -->
				<div class="col-md-6">
					<div class="card" style="padding: 20px;">
						<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
							<h5 style="margin: 0;">${__("Amazon")}</h5>
							<span class="indicator-pill ${amazon.enabled ? 'green' : 'red'}">
								${amazon.enabled ? __("Connected") : __("Disabled")}
							</span>
						</div>
						<div class="row">
							<div class="col-6">
								<div style="margin-bottom: 10px;">
									<span style="font-size: 24px; font-weight: bold;">${amazon.orders_today || 0}</span>
									<br><small class="text-muted">${__("Orders Today")}</small>
								</div>
							</div>
							<div class="col-6">
								<div style="margin-bottom: 10px;">
									<span style="font-size: 24px; font-weight: bold;">${amazon.orders_this_week || 0}</span>
									<br><small class="text-muted">${__("This Week")}</small>
								</div>
							</div>
							<div class="col-6">
								<div>
									<span style="font-size: 24px; font-weight: bold;">${amazon.total_products_synced || 0}</span>
									<br><small class="text-muted">${__("Products Synced")}</small>
								</div>
							</div>
							<div class="col-6">
								<div>
									<span style="font-size: 24px; font-weight: bold; color: ${amazon.errors_today > 0 ? 'var(--red)' : 'inherit'};">${amazon.errors_today || 0}</span>
									<br><small class="text-muted">${__("Errors Today")}</small>
								</div>
							</div>
						</div>
					</div>
				</div>
			</div>

			<!-- Recent Errors -->
			<div class="card" style="padding: 20px;">
				<h5 style="margin-bottom: 15px;">${__("Recent Errors")}</h5>
				${errors.length > 0 ? render_errors_table(errors) : '<p class="text-muted">' + __("No recent errors") + '</p>'}
			</div>
		</div>
	`;

	page.main.html(html);
}

function render_errors_table(errors) {
	let rows = errors
		.map(
			(e) => `
		<tr>
			<td><span class="indicator-pill red">${frappe.utils.escape_html(e.integration || "")}</span></td>
			<td>${frappe.utils.escape_html((e.message || "").substring(0, 120))}</td>
			<td>${frappe.datetime.prettyDate(e.creation)}</td>
			<td>
				<button class="btn btn-xs btn-default" onclick="frappe.call({method: 'ecom_bridge.api.dashboard.retry_failed_sync', args: {log_name: '${e.name}'}, callback: (r) => frappe.show_alert({message: 'Retry queued', indicator: 'green'})})">
					${__("Retry")}
				</button>
			</td>
		</tr>
	`
		)
		.join("");

	return `
		<table class="table table-bordered" style="margin: 0;">
			<thead>
				<tr>
					<th style="width: 120px;">${__("Platform")}</th>
					<th>${__("Error")}</th>
					<th style="width: 140px;">${__("When")}</th>
					<th style="width: 80px;">${__("Action")}</th>
				</tr>
			</thead>
			<tbody>${rows}</tbody>
		</table>
	`;
}

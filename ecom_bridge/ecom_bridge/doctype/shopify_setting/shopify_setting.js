// Copyright (c) 2021, Frappe and contributors
// For license information, please see LICENSE

frappe.provide("ecom_bridge.integrations.shopify.shopify_setting");

frappe.ui.form.on("Shopify Setting", {
	onload: function (frm) {
		frappe.call({
			method: "ecom_bridge.utils.naming_series.get_series",
			callback: function (r) {
				$.each(r.message, (key, value) => {
					set_field_options(key, value);
				});
			},
		});
	},

	bulk_map_items: function (frm) {
		frappe.call({
			doc: frm.doc,
			method: "bulk_map_items",
			freeze: true,
			freeze_message: __("Fetching Shopify products and mapping to ERPNext items..."),
			callback: function (r) {
				if (r.message) {
					let result = r.message;
					let msg = `<b>${__("Bulk Map Results")}</b><br><br>`;
					msg += `${__("Mapped")}: <b>${result.mapped}</b><br>`;
					msg += `${__("Already Mapped")}: <b>${result.skipped}</b><br>`;
					msg += `${__("Unmatched")}: <b>${result.unmatched}</b><br>`;

					if (result.details.unmatched.length > 0) {
						msg += `<br><b>${__("Unmatched Products")}:</b><br>`;
						result.details.unmatched.forEach(function (item) {
							msg += `- ${item.shopify_product} (SKU: ${item.sku || "N/A"})<br>`;
						});
					}

					frappe.msgprint({
						title: __("Bulk Map Items"),
						message: msg,
						indicator: result.unmatched > 0 ? "orange" : "green",
					});
				}
			},
		});
	},

	fetch_shopify_locations: function (frm) {
		frappe.call({
			doc: frm.doc,
			method: "update_location_table",
			callback: (r) => {
				if (!r.exc) refresh_field("shopify_warehouse_mapping");
			},
		});
	},

	refresh: function (frm) {
		frm.add_custom_button(__("Import Products"), function () {
			frappe.set_route("shopify-import-products");
		});
		frm.add_custom_button(__("View Logs"), () => {
			frappe.set_route("List", "Ecommerce Integration Log", {
				integration: "Shopify",
			});
		});
		frm.trigger("setup_queries");
	},

	setup_queries: function (frm) {
		const warehouse_query = () => {
			return {
				filters: {
					company: frm.doc.company,
					is_group: 0,
					disabled: 0,
				},
			};
		};
		frm.set_query("warehouse", warehouse_query);
		frm.set_query(
			"erpnext_warehouse",
			"shopify_warehouse_mapping",
			warehouse_query
		);

		frm.set_query("price_list", () => {
			return {
				filters: {
					selling: 1,
				},
			};
		});

		frm.set_query("cost_center", () => {
			return {
				filters: {
					company: frm.doc.company,
					is_group: "No",
				},
			};
		});

		frm.set_query("cash_bank_account", () => {
			return {
				filters: [
					["Account", "account_type", "in", ["Cash", "Bank"]],
					["Account", "root_type", "=", "Asset"],
					["Account", "is_group", "=", 0],
					["Account", "company", "=", frm.doc.company],
				],
			};
		});

		const tax_query = () => {
			return {
				query: "erpnext.controllers.queries.tax_account_query",
				filters: {
					account_type: ["Tax", "Chargeable", "Expense Account"],
					company: frm.doc.company,
				},
			};
		};

		frm.set_query("tax_account", "taxes", tax_query);
		frm.set_query("default_sales_tax_account", tax_query);
		frm.set_query("default_shipping_charges_account", tax_query);
	},
});

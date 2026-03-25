app_name = "ecom_bridge"
app_title = "Ecom Bridge"
app_publisher = "sammish"
app_description = "Standalone Shopify & Amazon ecommerce bridge for ERPNext — zero external dependencies"
app_email = "sammish.thundiyi@gmail.com"
app_license = "mit"

# Apps — only ERPNext required, NO ecommerce_integrations
# ------------------
required_apps = ["erpnext"]


# DocType JS
# ------------------
doctype_js = {
	"Sales Order": "public/js/common/ecommerce_transactions.js",
	"Sales Invoice": "public/js/common/ecommerce_transactions.js",
}


# Document Events
# ---------------
doc_events = {
	"Sales Order": {
		"validate": [
			"ecom_bridge.shopify.overrides.validate_sales_order",
			"ecom_bridge.amazon.overrides.validate_sales_order",
		],
		"on_submit": [
			"ecom_bridge.shopify.overrides.on_submit_sales_order",
			"ecom_bridge.amazon.overrides.on_submit_sales_order",
		],
		"after_insert": "ecom_bridge.amazon.order.after_amazon_order_sync",
	},
	"Sales Invoice": {
		"validate": [
			"ecom_bridge.shopify.overrides.validate_sales_invoice",
			"ecom_bridge.amazon.overrides.validate_sales_invoice",
		],
		"on_submit": [
			"ecom_bridge.shopify.overrides.on_submit_sales_invoice",
			"ecom_bridge.amazon.overrides.on_submit_sales_invoice",
		],
	},
	"Delivery Note": {
		"validate": "ecom_bridge.shopify.fulfillment.validate_delivery_note",
		"on_submit": [
			"ecom_bridge.shopify.fulfillment.on_submit_delivery_note",
			"ecom_bridge.amazon.fulfillment.create_fulfillment_for_amazon",
		],
	},
	"Customer": {
		"after_insert": [
			"ecom_bridge.shopify.overrides.after_insert_customer",
			"ecom_bridge.amazon.overrides.after_insert_customer",
		],
	},
	"Item": {
		"after_insert": "ecom_bridge.integrations.shopify.product.upload_erpnext_item",
		"on_update": [
			"ecom_bridge.integrations.shopify.product.upload_erpnext_item",
			"ecom_bridge.shopify.product.after_product_sync",
		],
		"validate": [
			"ecom_bridge.shopify.overrides.validate_item",
			"ecom_bridge.amazon.overrides.validate_item",
		],
	},
}


# Scheduled Tasks
# ---------------
scheduler_events = {
	"all": [
		"ecom_bridge.integrations.shopify.inventory.update_inventory_on_shopify",
	],
	"daily": [
		"ecom_bridge.shopify.sync.daily_sync_cleanup",
	],
	"hourly": [
		"ecom_bridge.integrations.shopify.order.sync_old_orders",
		"ecom_bridge.ecom_bridge.doctype.amazon_sp_api_settings.amazon_sp_api_settings.schedule_get_order_details",
		"ecom_bridge.shopify.sync.sync_health_check",
		"ecom_bridge.amazon.returns.process_amazon_returns",
		"ecom_bridge.utils.payment.reconcile_shopify_payments",
		"ecom_bridge.utils.payment.reconcile_amazon_payments",
	],
	"cron": {
		"*/5 * * * *": [
			"ecom_bridge.amazon.notifications.poll_amazon_notifications",
		],
		"*/15 * * * *": [
			"ecom_bridge.amazon.fulfillment.process_pending_fulfillments",
		],
		"*/30 * * * *": [
			"ecom_bridge.shopify.inventory.validate_inventory_before_sync",
			"ecom_bridge.amazon.inventory.sync_inventory_to_amazon",
		],
	},
}


# Fixtures — export custom fields added by this app
# ---------------------------------------------------
fixtures = [
	{
		"dt": "Custom Field",
		"filters": [["module", "=", "Ecom Bridge"]],
	},
]


# Installation
# ------------
after_install = "ecom_bridge.setup.after_install"
after_migrate = "ecom_bridge.setup.after_migrate"

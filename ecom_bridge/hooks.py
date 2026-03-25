app_name = "ecom_bridge"
app_title = "Ecom Bridge"
app_publisher = "sammish"
app_description = "Custom ecommerce bridge for Shopify & Amazon integrations with ERPNext"
app_email = "sammish.thundiyi@gmail.com"
app_license = "mit"

# Apps
# ------------------
required_apps = ["frappe/erpnext", "frappe/ecommerce_integrations"]


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
		"validate": [
			"ecom_bridge.shopify.overrides.validate_item",
			"ecom_bridge.amazon.overrides.validate_item",
		],
		"on_update": "ecom_bridge.shopify.product.after_product_sync",
	},
}


# Scheduled Tasks
# ---------------
scheduler_events = {
	"daily": [
		"ecom_bridge.shopify.sync.daily_sync_cleanup",
	],
	"hourly": [
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


# Overriding Methods from ecommerce_integrations
# ------------------------------------------------
override_whitelisted_methods = {
	"ecommerce_integrations.shopify.order.create_sales_order": "ecom_bridge.shopify.order.custom_create_sales_order",
}


# Fixtures — export custom fields added by this app
# ---------------------------------------------------
fixtures = [
	{
		"dt": "Custom Field",
		"filters": [["module", "=", "Ecom Bridge"]],
	},
	{
		"dt": "Page",
		"filters": [["module", "=", "Ecom Bridge"]],
	},
]


# Installation
# ------------
after_install = "ecom_bridge.setup.after_install"
after_migrate = "ecom_bridge.setup.after_migrate"

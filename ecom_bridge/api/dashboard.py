import frappe
from frappe.utils import add_days, nowdate, now_datetime, flt


@frappe.whitelist()
def get_sync_dashboard():
	"""
	Get sync status dashboard data for both Shopify and Amazon.

	Returns:
		dict with sync stats for both platforms
	"""
	return {
		"shopify": _get_shopify_stats(),
		"amazon": _get_amazon_stats(),
		"recent_errors": _get_recent_errors(),
		"summary": _get_summary(),
	}


@frappe.whitelist()
def get_sync_logs(integration=None, status=None, limit=50):
	"""
	Get recent sync logs filtered by integration and status.

	Args:
		integration: 'shopify' or 'amazon'
		status: 'Success', 'Error', 'Skipped'
		limit: max records to return
	"""
	filters = {}
	if integration:
		filters["integration"] = integration.lower()
	if status:
		filters["status"] = status

	logs = frappe.get_list(
		"Ecommerce Integration Log",
		filters=filters,
		fields=["name", "integration", "status", "message", "creation", "method"],
		order_by="creation desc",
		limit_page_length=min(int(limit), 200),
	)
	return logs


@frappe.whitelist()
def retry_failed_sync(log_name):
	"""Retry a failed sync operation."""
	log = frappe.get_doc("Ecommerce Integration Log", log_name)
	if log.status != "Error":
		frappe.throw("Can only retry failed sync operations")

	if log.integration == "shopify":
		_retry_shopify_sync(log)
	elif log.integration == "amazon":
		_retry_amazon_sync(log)

	return {"status": "queued", "message": f"Retry queued for {log_name}"}


@frappe.whitelist()
def force_sync(integration):
	"""Trigger a manual sync for the specified integration."""
	if integration == "shopify":
		frappe.enqueue(
			"ecom_bridge.integrations.shopify.order.sync_old_orders",
			queue="short",
			timeout=600,
		)
		return {"status": "queued", "message": "Shopify order sync queued"}

	elif integration == "amazon":
		if frappe.db.exists("DocType", "Amazon SP API Settings"):
			frappe.enqueue(
				"ecom_bridge.ecom_bridge.doctype.amazon_sp_api_settings"
				".amazon_sp_api_settings.schedule_get_order_details",
				queue="short",
				timeout=600,
			)
			return {"status": "queued", "message": "Amazon order sync queued"}

	frappe.throw(f"Unknown integration: {integration}")


@frappe.whitelist()
def force_inventory_sync():
	"""Manually trigger inventory sync to Shopify, bypassing the scheduler interval."""
	from ecom_bridge.integrations.shopify.constants import SETTING_DOCTYPE

	setting = frappe.get_doc(SETTING_DOCTYPE)
	if not setting.is_enabled() or not setting.update_erpnext_stock_levels_to_shopify:
		frappe.throw("Shopify inventory sync is not enabled in Shopify Setting")

	warehous_map = setting.get_erpnext_to_integration_wh_mapping()
	if not warehous_map:
		frappe.throw("No warehouse mapping configured in Shopify Setting")

	from ecom_bridge.controllers.inventory import get_inventory_levels
	from ecom_bridge.integrations.shopify.constants import MODULE_NAME

	inventory_levels = get_inventory_levels(tuple(warehous_map.keys()), MODULE_NAME)

	if not inventory_levels:
		return {"status": "skipped", "message": "No inventory changes to sync"}

	frappe.enqueue(
		"ecom_bridge.integrations.shopify.inventory.upload_inventory_data_to_shopify",
		queue="short",
		timeout=300,
		inventory_levels=inventory_levels,
		warehous_map=warehous_map,
	)

	return {
		"status": "queued",
		"message": f"Inventory sync queued for {len(inventory_levels)} items",
	}


@frappe.whitelist()
def force_fulfillment_sync(delivery_note):
	"""Manually trigger fulfillment sync for a specific Delivery Note."""
	dn = frappe.get_doc("Delivery Note", delivery_note)
	if dn.docstatus != 1:
		frappe.throw("Delivery Note must be submitted before syncing fulfillment")

	if dn.get("shopify_fulfillment_id"):
		frappe.throw("This Delivery Note already has a Shopify fulfillment ID")

	from ecom_bridge.shopify.fulfillment import _get_shopify_order_id

	shopify_order_id = _get_shopify_order_id(dn)
	if not shopify_order_id:
		frappe.throw("No Shopify order linked to this Delivery Note")

	frappe.enqueue(
		"ecom_bridge.shopify.fulfillment.create_fulfillment_on_shopify",
		queue="short",
		timeout=120,
		shopify_order_id=shopify_order_id,
		delivery_note=delivery_note,
	)

	return {
		"status": "queued",
		"message": f"Fulfillment sync queued for Shopify order {shopify_order_id}",
	}


def _get_shopify_stats():
	"""Get Shopify-specific sync statistics."""
	today = nowdate()
	week_ago = add_days(today, -7)

	orders_today = frappe.db.count(
		"Sales Order",
		filters={
			"shopify_order_id": ["is", "set"],
			"creation": (">=", today),
		},
	)

	orders_week = frappe.db.count(
		"Sales Order",
		filters={
			"shopify_order_id": ["is", "set"],
			"creation": (">=", week_ago),
		},
	)

	errors_today = frappe.db.count(
		"Ecommerce Integration Log",
		filters={
			"integration": "shopify",
			"status": "Error",
			"creation": (">=", today),
		},
	)

	total_products = frappe.db.count(
		"Ecommerce Item",
		filters={"integration": "shopify"},
	)

	return {
		"orders_today": orders_today,
		"orders_this_week": orders_week,
		"errors_today": errors_today,
		"total_products_synced": total_products,
		"enabled": _is_shopify_enabled(),
	}


def _get_amazon_stats():
	"""Get Amazon-specific sync statistics."""
	today = nowdate()
	week_ago = add_days(today, -7)

	orders_today = frappe.db.count(
		"Sales Order",
		filters={
			"amazon_order_id": ["is", "set"],
			"creation": (">=", today),
		},
	)

	orders_week = frappe.db.count(
		"Sales Order",
		filters={
			"amazon_order_id": ["is", "set"],
			"creation": (">=", week_ago),
		},
	)

	errors_today = frappe.db.count(
		"Ecommerce Integration Log",
		filters={
			"integration": "amazon",
			"status": "Error",
			"creation": (">=", today),
		},
	)

	total_products = frappe.db.count(
		"Ecommerce Item",
		filters={"integration": "amazon"},
	)

	return {
		"orders_today": orders_today,
		"orders_this_week": orders_week,
		"errors_today": errors_today,
		"total_products_synced": total_products,
		"enabled": _is_amazon_enabled(),
	}


def _get_recent_errors(limit=10):
	"""Get most recent error logs across all integrations."""
	return frappe.get_list(
		"Ecommerce Integration Log",
		filters={"status": "Error"},
		fields=["name", "integration", "message", "creation"],
		order_by="creation desc",
		limit_page_length=limit,
	)


def _get_summary():
	"""Get overall summary stats."""
	today = nowdate()
	return {
		"total_orders_today": frappe.db.count(
			"Sales Order",
			filters={
				"creation": (">=", today),
				"marketplace_source": ["in", ["Shopify", "Amazon"]],
			},
		) if frappe.db.has_column("Sales Order", "marketplace_source") else 0,
		"total_errors_today": frappe.db.count(
			"Ecommerce Integration Log",
			filters={
				"status": "Error",
				"creation": (">=", today),
			},
		),
		"last_sync": frappe.db.get_value(
			"Ecommerce Integration Log",
			filters={"status": "Success"},
			fieldname="creation",
			order_by="creation desc",
		),
	}


def _is_shopify_enabled():
	"""Check if Shopify integration is enabled."""
	if frappe.db.exists("DocType", "Shopify Setting"):
		return bool(frappe.db.get_single_value("Shopify Setting", "enable_shopify"))
	return False


def _is_amazon_enabled():
	"""Check if Amazon integration is enabled."""
	if frappe.db.exists("DocType", "Amazon SP API Settings"):
		return bool(frappe.db.get_single_value("Amazon SP API Settings", "enable_sync"))
	return False


def _retry_shopify_sync(log):
	"""Retry a failed Shopify sync."""
	frappe.enqueue(
		"ecom_bridge.integrations.shopify.order.sync_old_orders",
		queue="short",
		timeout=300,
	)


def _retry_amazon_sync(log):
	"""Retry a failed Amazon sync."""
	if frappe.db.exists("DocType", "Amazon SP API Settings"):
		frappe.enqueue(
			"ecom_bridge.ecom_bridge.doctype.amazon_sp_api_settings"
			".amazon_sp_api_settings.schedule_get_order_details",
			queue="short",
			timeout=300,
		)

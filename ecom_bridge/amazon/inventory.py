"""
Amazon inventory sync — push ERPNext stock levels to Amazon.

Uses SP-API Feeds API to submit inventory updates.
"""

import json

import frappe
from frappe import _
from frappe.utils import flt, now_datetime

from ecom_bridge.utils.logger import log_error, log_info


def validate_inventory_before_sync():
	"""Pre-validation before pushing inventory to Amazon."""
	from ecom_bridge.amazon.overrides import get_bridge_settings

	settings = get_bridge_settings()
	if not settings or not settings.sync_inventory_to_amazon:
		return

	_check_negative_stock(settings)


def sync_inventory_to_amazon():
	"""
	Push ERPNext inventory levels to Amazon via SP-API Feeds.

	Flow:
	1. Get all items linked to Amazon via Ecommerce Item
	2. Calculate available qty (actual - reserved) per item
	3. Build inventory feed JSON
	4. Submit feed via SP-API Feeds API
	"""
	from ecom_bridge.amazon.overrides import get_bridge_settings

	settings = get_bridge_settings()
	if not settings or not settings.sync_inventory_to_amazon:
		return

	if not frappe.db.exists("DocType", "Amazon SP API Settings"):
		return

	amazon_settings = frappe.get_single("Amazon SP API Settings")
	if not amazon_settings.enable_sync:
		return

	warehouse = settings.get_amazon_warehouse()
	if not warehouse:
		log_error("Amazon", "No warehouse configured for Amazon inventory sync")
		return

	# Get all items linked to Amazon
	amazon_items = frappe.db.sql(
		"""
		SELECT ei.erpnext_item_code, ei.integration_item_code, ei.sku
		FROM `tabEcommerce Item` ei
		WHERE ei.integration = 'amazon'
		AND ei.erpnext_item_code IS NOT NULL
		""",
		as_dict=True,
	)

	if not amazon_items:
		return

	# Build inventory feed
	inventory_updates = []
	error_count = 0

	for item in amazon_items:
		try:
			actual_qty = flt(
				frappe.db.get_value(
					"Bin",
					{"item_code": item.erpnext_item_code, "warehouse": warehouse},
					"actual_qty",
				)
			)
			reserved_qty = flt(
				frappe.db.get_value(
					"Bin",
					{"item_code": item.erpnext_item_code, "warehouse": warehouse},
					"reserved_qty",
				)
			)

			available_qty = max(0, int(actual_qty - reserved_qty))

			sku = item.sku or item.integration_item_code
			if sku:
				inventory_updates.append({
					"sku": sku,
					"quantity": available_qty,
					"item_code": item.erpnext_item_code,
				})

		except Exception as e:
			error_count += 1
			log_error("Amazon", f"Inventory calc failed for {item.erpnext_item_code}: {e}")

	if not inventory_updates:
		return

	# Submit to Amazon via SP-API
	try:
		_submit_inventory_feed(inventory_updates, amazon_settings)
	except Exception as e:
		log_error("Amazon", f"Inventory feed submission failed: {e}", exception=e)

	log_info(
		"Amazon",
		f"Inventory sync: {len(inventory_updates)} items prepared, {error_count} errors",
	)


def _submit_inventory_feed(inventory_updates, amazon_settings):
	"""Submit inventory feed to Amazon SP-API."""
	from ecom_bridge.amazon.sp_api_client import Feeds, get_sp_api_instance, call_sp_api_with_retry

	feeds_api = get_sp_api_instance(Feeds)
	if not feeds_api:
		log_error("Amazon", "Could not initialize Feeds API for inventory sync")
		return

	# Build JSON feed content
	# Amazon JSON_LISTINGS_FEED format
	messages = []
	for idx, update in enumerate(inventory_updates, 1):
		messages.append({
			"messageId": idx,
			"sku": update["sku"],
			"operationType": "PATCH",
			"body": {
				"patches": [
					{
						"op": "replace",
						"path": "/attributes/fulfillment_availability",
						"value": [
							{
								"fulfillment_channel_code": "DEFAULT",
								"quantity": update["quantity"],
							}
						],
					}
				]
			},
		})

	feed_content = {
		"header": {
			"sellerId": "",  # Auto-populated by Amazon
			"version": "2.0",
			"issueLocale": "en_US",
		},
		"messages": messages,
	}

	marketplace_id = feeds_api.marketplace_id

	result = call_sp_api_with_retry(
		feeds_api.create_feed,
		max_retries=3,
		feed_type="JSON_LISTINGS_FEED",
		marketplace_ids=[marketplace_id],
		content=feed_content,
		content_type="application/json",
	)

	if result:
		feed_id = result.get("feedId") if isinstance(result, dict) else None
		log_info(
			"Amazon",
			f"Inventory feed submitted successfully. Feed ID: {feed_id}. "
			f"Items: {len(inventory_updates)}",
		)
	else:
		log_error("Amazon", "Inventory feed submission returned no result")


def _check_negative_stock(settings):
	"""Warn about negative stock items."""
	warehouse = settings.get_amazon_warehouse()
	if not warehouse:
		return

	negative_count = frappe.db.count(
		"Bin",
		filters={"warehouse": warehouse, "actual_qty": ("<", 0)},
	)

	if negative_count:
		log_info(
			"Amazon",
			f"Found {negative_count} items with negative stock in {warehouse}. "
			"These will be synced as 0 quantity.",
		)

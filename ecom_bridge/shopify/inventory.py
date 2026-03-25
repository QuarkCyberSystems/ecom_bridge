import frappe
from frappe import _
from frappe.utils import flt, now_datetime

from ecom_bridge.utils.logger import log_error, log_info


def validate_inventory_before_sync():
	"""
	Pre-validation before pushing inventory to Shopify.
	Called by scheduler before the inventory sync runs.
	"""
	from ecom_bridge.shopify.overrides import get_bridge_settings

	settings = get_bridge_settings()
	if not settings or not settings.sync_inventory_to_shopify:
		return

	_check_negative_stock(settings)
	_check_warehouse_mapping(settings)


def after_inventory_sync():
	"""Post-sync tasks — logging and notification."""
	from ecom_bridge.shopify.overrides import get_bridge_settings

	settings = get_bridge_settings()
	if not settings:
		return

	log_info("Shopify", f"Inventory sync completed at {now_datetime()}")


def _check_negative_stock(settings):
	"""Warn about negative stock items that will be synced as 0."""
	warehouse = settings.get_shopify_warehouse()
	if not warehouse:
		return

	negative_items = frappe.db.sql(
		"""
		SELECT item_code, actual_qty
		FROM `tabBin`
		WHERE warehouse = %s AND actual_qty < 0
		LIMIT 20
		""",
		warehouse,
		as_dict=True,
	)

	if negative_items:
		items_list = ", ".join([d.item_code for d in negative_items[:5]])
		log_info(
			"Shopify",
			f"Found {len(negative_items)} items with negative stock in {warehouse}. "
			f"These will be synced as 0. Items: {items_list}...",
		)


def _check_warehouse_mapping(settings):
	"""Verify warehouse mapping is properly configured."""
	shopify_setting = frappe.get_single("Shopify Setting")
	if not shopify_setting.get("shopify_warehouse_mapping"):
		log_error(
			"Shopify",
			"No warehouse mapping configured in Shopify Setting. "
			"Inventory sync may use wrong locations.",
		)

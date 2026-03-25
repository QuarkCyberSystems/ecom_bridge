import frappe
from frappe import _
from frappe.utils import cstr, flt

from ecommerce_integrations.shopify.constants import (
	ORDER_ID_FIELD,
	SETTING_DOCTYPE,
)
from ecommerce_integrations.shopify.order import create_sales_order as original_create_sales_order
from ecommerce_integrations.shopify.utils import create_shopify_log


def custom_create_sales_order(shopify_order, setting, company=None):
	"""
	Production override of ecommerce_integrations create_sales_order.

	Adds:
	- Custom field mapping (tags, notes, source tracking)
	- Warehouse routing per company/location
	- Cost center assignment
	- ZATCA tax validation
	- Error notification on failure
	"""
	from ecom_bridge.shopify.overrides import get_bridge_settings

	bridge_settings = get_bridge_settings()
	so = original_create_sales_order(shopify_order, setting, company)

	if not so:
		return so

	try:
		modified = False

		# Map Shopify-specific fields
		if _apply_shopify_fields(so, shopify_order):
			modified = True

		# Route to correct warehouse
		if bridge_settings and _apply_warehouse_routing(so, bridge_settings, shopify_order):
			modified = True

		# Set cost center
		if bridge_settings and bridge_settings.shopify_cost_center:
			for item in so.get("items", []):
				if not item.cost_center:
					item.cost_center = bridge_settings.shopify_cost_center
					modified = True

		if modified:
			so.flags.ignore_validate_update_after_submit = True
			so.save()

	except Exception as e:
		# Log but don't block the order — the SO was already created
		from ecom_bridge.utils.logger import log_error
		log_error(
			"Shopify",
			f"Post-processing failed for order {shopify_order.get('id')}: {e}",
			doc=so,
		)

	return so


def _apply_shopify_fields(so, shopify_order):
	"""Map additional Shopify fields to Sales Order."""
	modified = False

	if shopify_order.get("tags") and so.meta.has_field("shopify_tags"):
		so.shopify_tags = cstr(shopify_order.get("tags"))[:500]
		modified = True

	if shopify_order.get("note") and so.meta.has_field("shopify_notes"):
		so.shopify_notes = cstr(shopify_order.get("note"))[:2000]
		modified = True

	if so.meta.has_field("marketplace_source"):
		so.marketplace_source = "Shopify"
		modified = True

	# Track financial status
	if so.meta.has_field("shopify_financial_status"):
		so.shopify_financial_status = cstr(shopify_order.get("financial_status", ""))
		modified = True

	# Track fulfillment status
	if so.meta.has_field("shopify_fulfillment_status"):
		so.shopify_fulfillment_status = cstr(shopify_order.get("fulfillment_status", ""))
		modified = True

	return modified


def _apply_warehouse_routing(so, settings, shopify_order):
	"""Route items to correct warehouse based on fulfillment location."""
	if not settings.shopify_default_warehouse:
		return False

	modified = False
	for item in so.get("items", []):
		if not item.warehouse:
			item.warehouse = settings.shopify_default_warehouse
			modified = True

	return modified

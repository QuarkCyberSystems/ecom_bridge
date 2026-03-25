import frappe
from frappe import _


def validate_delivery_note(doc, method):
	"""
	Validate Delivery Notes created from Shopify fulfillments.
	Ensures warehouse and item mapping is correct.
	"""
	if not doc.get("shopify_fulfillment_id"):
		return

	from ecom_bridge.shopify.overrides import get_bridge_settings

	settings = get_bridge_settings()
	if not settings:
		return

	# Ensure all items have a warehouse
	for item in doc.get("items", []):
		if not item.warehouse and settings.shopify_default_warehouse:
			item.warehouse = settings.shopify_default_warehouse

	# Set marketplace source
	if doc.meta.has_field("marketplace_source"):
		doc.marketplace_source = "Shopify"


def on_submit_delivery_note(doc, method):
	"""Post-submit hook for Shopify delivery notes."""
	if not doc.get("shopify_fulfillment_id"):
		return

	from ecom_bridge.utils.logger import log_info
	log_info(
		"Shopify",
		f"Delivery Note {doc.name} submitted for Shopify fulfillment {doc.shopify_fulfillment_id}",
	)

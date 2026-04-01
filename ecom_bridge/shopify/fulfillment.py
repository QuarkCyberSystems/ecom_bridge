import frappe
from frappe import _

from ecom_bridge.utils.logger import log_error, log_info


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
	# Case 1: DN created FROM Shopify webhook (already fulfilled in Shopify)
	if doc.get("shopify_fulfillment_id"):
		log_info(
			"Shopify",
			f"Delivery Note {doc.name} submitted for Shopify fulfillment {doc.shopify_fulfillment_id}",
		)
		return

	# Case 2: DN created in ERPNext — push fulfillment TO Shopify
	_maybe_fulfill_on_shopify(doc)


def _maybe_fulfill_on_shopify(doc):
	"""If enabled, mark the linked Shopify order as fulfilled."""
	from ecom_bridge.shopify.overrides import get_bridge_settings

	settings = get_bridge_settings()
	if not settings or not settings.sync_fulfillment_to_shopify:
		return

	# Find the Shopify order ID from the linked Sales Order
	shopify_order_id = _get_shopify_order_id(doc)
	if not shopify_order_id:
		return

	frappe.enqueue(
		"ecom_bridge.shopify.fulfillment.create_fulfillment_on_shopify",
		queue="short",
		timeout=120,
		shopify_order_id=shopify_order_id,
		delivery_note=doc.name,
	)

	log_info(
		"Shopify",
		f"Fulfillment queued for Shopify order {shopify_order_id} "
		f"via Delivery Note {doc.name}",
	)


def _get_shopify_order_id(doc):
	"""Extract Shopify order ID from the Delivery Note's linked Sales Order."""
	# Check if DN itself has the shopify_order_id field
	if doc.get("shopify_order_id"):
		return doc.shopify_order_id

	# Otherwise check the linked Sales Order
	for item in doc.get("items", []):
		so_name = item.get("against_sales_order")
		if so_name:
			order_id = frappe.db.get_value("Sales Order", so_name, "shopify_order_id")
			if order_id:
				return order_id

	return None


def create_fulfillment_on_shopify(shopify_order_id, delivery_note):
	"""
	Create a fulfillment in Shopify for the given order.

	Uses the FulfillmentOrder-based API (2024-01+):
	1. Get fulfillment orders for the Shopify order
	2. Create a fulfillment via FulfillmentV2

	Called as a background job from on_submit_delivery_note.
	"""
	from ecom_bridge.integrations.shopify.connection import temp_shopify_session
	from ecom_bridge.integrations.shopify.utils import create_shopify_log

	@temp_shopify_session
	def _do_fulfill():
		try:
			from shopify.resources import FulfillmentOrders
			from shopify.resources.fulfillment import FulfillmentV2

			# Get open fulfillment orders for this Shopify order
			fulfillment_orders = FulfillmentOrders.find(order_id=shopify_order_id)

			open_fo = [
				fo for fo in fulfillment_orders
				if fo.status in ("open", "in_progress")
			]

			if not open_fo:
				log_info(
					"Shopify",
					f"No open fulfillment orders for Shopify order {shopify_order_id}. "
					f"Order may already be fulfilled.",
				)
				return

			# Build the fulfillment request using fulfillment order line items
			line_items_by_fo = [
				{"fulfillment_order_id": fo.id}
				for fo in open_fo
			]

			fulfillment = FulfillmentV2()
			fulfillment.line_items_by_fulfillment_order = line_items_by_fo
			fulfillment.notify_customer = True

			success = fulfillment.save()

			if success:
				# Store the Shopify fulfillment ID back on the Delivery Note
				frappe.db.set_value(
					"Delivery Note",
					delivery_note,
					"shopify_fulfillment_id",
					str(fulfillment.id),
				)

				log_info(
					"Shopify",
					f"Fulfillment {fulfillment.id} created for order {shopify_order_id}, "
					f"DN: {delivery_note}",
				)
				create_shopify_log(status="Success")
			else:
				error_msg = str(fulfillment.errors.full_messages()) if fulfillment.errors else "Unknown error"
				log_error(
					"Shopify",
					f"Failed to create fulfillment for order {shopify_order_id}: {error_msg}. "
					f"DN: {delivery_note}",
				)
				create_shopify_log(status="Error", message=error_msg)

		except Exception as e:
			log_error(
				"Shopify",
				f"Error creating fulfillment for order {shopify_order_id}: {e}. "
				f"DN: {delivery_note}",
			)
			create_shopify_log(status="Error", exception=e, rollback=True)

	_do_fulfill()

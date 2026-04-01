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

	Uses direct REST API calls to:
	1. Get fulfillment orders for the Shopify order
	2. Create a fulfillment from the open fulfillment orders

	Called as a background job from on_submit_delivery_note.
	"""
	import json
	from urllib.error import HTTPError
	from urllib.request import Request, urlopen

	from ecom_bridge.integrations.shopify.constants import API_VERSION, SETTING_DOCTYPE
	from ecom_bridge.integrations.shopify.utils import create_shopify_log

	try:
		setting = frappe.get_doc(SETTING_DOCTYPE)
		shop_url = setting.shopify_url.replace("https://", "")
		token = setting.get_password("password")
		base = f"https://{shop_url}/admin/api/{API_VERSION}"
		headers = {
			"X-Shopify-Access-Token": token,
			"Content-Type": "application/json",
		}

		# Step 1: Get fulfillment orders
		req = Request(
			f"{base}/orders/{shopify_order_id}/fulfillment_orders.json",
			headers=headers,
		)
		resp = urlopen(req)
		fo_data = json.loads(resp.read())

		open_fo = [
			fo for fo in fo_data.get("fulfillment_orders", [])
			if fo["status"] in ("open", "in_progress")
		]

		if not open_fo:
			log_info(
				"Shopify",
				f"No open fulfillment orders for Shopify order {shopify_order_id}. "
				f"Order may already be fulfilled.",
			)
			return

		# Step 2: Create fulfillment
		line_items_by_fo = [
			{"fulfillment_order_id": fo["id"]}
			for fo in open_fo
		]

		payload = json.dumps({
			"fulfillment": {
				"line_items_by_fulfillment_order": line_items_by_fo,
				"notify_customer": True,
			}
		}).encode()

		req = Request(
			f"{base}/fulfillments.json",
			data=payload,
			headers=headers,
			method="POST",
		)
		resp = urlopen(req)
		result = json.loads(resp.read())
		fulfillment_id = result["fulfillment"]["id"]

		# Store the Shopify fulfillment ID back on the Delivery Note
		frappe.db.set_value(
			"Delivery Note",
			delivery_note,
			"shopify_fulfillment_id",
			str(fulfillment_id),
		)

		log_info(
			"Shopify",
			f"Fulfillment {fulfillment_id} created for order {shopify_order_id}, "
			f"DN: {delivery_note}",
		)
		create_shopify_log(status="Success")

	except HTTPError as e:
		error_body = e.read().decode() if e.fp else str(e)
		log_error(
			"Shopify",
			f"Failed to create fulfillment for order {shopify_order_id}: "
			f"HTTP {e.code} — {error_body}. DN: {delivery_note}",
		)
		create_shopify_log(status="Error", message=f"HTTP {e.code}: {error_body}")

	except Exception as e:
		log_error(
			"Shopify",
			f"Error creating fulfillment for order {shopify_order_id}: {e}. "
			f"DN: {delivery_note}",
		)
		create_shopify_log(status="Error", exception=e, rollback=True)

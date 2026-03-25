"""
Amazon fulfillment — confirm shipments via SP-API when Delivery Notes are submitted.
"""

import frappe
from frappe import _

from ecom_bridge.utils.logger import log_error, log_info


def create_fulfillment_for_amazon(doc, method):
	"""
	When a Delivery Note is submitted for an Amazon order,
	queue fulfillment confirmation to Amazon SP-API.

	Hooks into Delivery Note on_submit.
	"""
	if not doc.get("items"):
		return

	# Get the linked Sales Order
	so_name = doc.items[0].against_sales_order if doc.items else None
	if not so_name:
		return

	amazon_order_id = frappe.db.get_value("Sales Order", so_name, "amazon_order_id")
	if not amazon_order_id:
		return

	from ecom_bridge.amazon.overrides import get_bridge_settings

	settings = get_bridge_settings()
	if not settings:
		return

	try:
		# Prepare fulfillment items
		fulfillment_items = []
		for item in doc.get("items", []):
			ecom_item = frappe.db.get_value(
				"Ecommerce Item",
				{"erpnext_item_code": item.item_code, "integration": "amazon"},
				["integration_item_code", "sku"],
				as_dict=True,
			)
			if ecom_item:
				fulfillment_items.append({
					"sku": ecom_item.sku or ecom_item.integration_item_code,
					"qty": item.qty,
				})

		if not fulfillment_items:
			return

		# Enqueue the actual API call as background job
		frappe.enqueue(
			"ecom_bridge.amazon.fulfillment.submit_fulfillment_to_amazon",
			queue="short",
			timeout=120,
			amazon_order_id=amazon_order_id,
			delivery_note=doc.name,
			items=fulfillment_items,
			tracking_number=doc.get("tracking_number", ""),
			carrier=doc.get("carrier", ""),
		)

		log_info(
			"Amazon",
			f"Fulfillment queued for Amazon order {amazon_order_id} "
			f"via Delivery Note {doc.name} ({len(fulfillment_items)} items)",
		)

	except Exception as e:
		log_error(
			"Amazon",
			f"Failed to prepare fulfillment for Amazon order {amazon_order_id}: {e}",
			doc=doc,
		)


def submit_fulfillment_to_amazon(amazon_order_id, delivery_note, items,
								  tracking_number="", carrier=""):
	"""
	Submit fulfillment confirmation to Amazon SP-API.

	For MFN (Merchant Fulfilled Network) orders, this confirms shipment.
	For FBA orders, Amazon handles fulfillment — we just log it.

	Called as a background job from create_fulfillment_for_amazon.
	"""
	from ecom_bridge.amazon.sp_api_client import (
		Fulfillment,
		get_sp_api_instance,
		call_sp_api_with_retry,
	)

	# Check if this is an FBA or MFN order
	fulfillment_channel = frappe.db.get_value(
		"Sales Order",
		{"amazon_order_id": amazon_order_id},
		"amazon_fulfillment_channel",
	)

	if fulfillment_channel == "FBA":
		log_info(
			"Amazon",
			f"Order {amazon_order_id} is FBA — Amazon handles fulfillment. "
			f"DN {delivery_note} logged only.",
		)
		return

	# MFN order — submit shipment confirmation
	fulfillment_api = get_sp_api_instance(Fulfillment)
	if not fulfillment_api:
		log_error("Amazon", "Could not initialize Fulfillment API")
		return

	result = call_sp_api_with_retry(
		fulfillment_api.update_shipment_status,
		max_retries=3,
		order_id=amazon_order_id,
		tracking_number=tracking_number,
		carrier=carrier,
	)

	if result is not None:
		log_info(
			"Amazon",
			f"Fulfillment confirmed for order {amazon_order_id}, "
			f"DN: {delivery_note}, tracking: {tracking_number or 'N/A'}",
		)
	else:
		log_error(
			"Amazon",
			f"Fulfillment confirmation failed for order {amazon_order_id} "
			f"after all retries. DN: {delivery_note}",
		)


def process_pending_fulfillments():
	"""
	Scheduled task to retry any failed fulfillment submissions.
	Runs every 15 minutes.
	"""
	from ecom_bridge.amazon.overrides import get_bridge_settings

	settings = get_bridge_settings()
	if not settings:
		return

	# Check for Delivery Notes linked to Amazon orders that haven't been confirmed
	unconfirmed = frappe.db.sql(
		"""
		SELECT dn.name, so.amazon_order_id
		FROM `tabDelivery Note` dn
		JOIN `tabDelivery Note Item` dni ON dni.parent = dn.name
		JOIN `tabSales Order` so ON so.name = dni.against_sales_order
		WHERE so.amazon_order_id IS NOT NULL
		AND so.amazon_order_id != ''
		AND dn.docstatus = 1
		AND dn.creation > DATE_SUB(NOW(), INTERVAL 7 DAY)
		GROUP BY dn.name, so.amazon_order_id
		LIMIT 20
		""",
		as_dict=True,
	)

	if not unconfirmed:
		return

	processed = 0
	for row in unconfirmed:
		try:
			dn = frappe.get_doc("Delivery Note", row.name)
			items = []
			for item in dn.get("items", []):
				ecom_item = frappe.db.get_value(
					"Ecommerce Item",
					{"erpnext_item_code": item.item_code, "integration": "amazon"},
					["integration_item_code", "sku"],
					as_dict=True,
				)
				if ecom_item:
					items.append({
						"sku": ecom_item.sku or ecom_item.integration_item_code,
						"qty": item.qty,
					})

			if items:
				submit_fulfillment_to_amazon(
					amazon_order_id=row.amazon_order_id,
					delivery_note=row.name,
					items=items,
					tracking_number=dn.get("tracking_number", ""),
					carrier=dn.get("carrier", ""),
				)
				processed += 1
		except Exception as e:
			log_error("Amazon", f"Failed to retry fulfillment for {row.name}: {e}")

	if processed:
		log_info("Amazon", f"Retried {processed} pending fulfillments")

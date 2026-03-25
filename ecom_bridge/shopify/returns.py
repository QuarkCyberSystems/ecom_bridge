"""
Shopify returns and refund handling.

Processes Shopify refund webhooks and creates Credit Notes / Return entries in ERPNext.
"""

import json

import frappe
from frappe import _
from frappe.utils import cstr, flt, getdate, nowdate

from ecom_bridge.integrations.shopify.constants import ORDER_ID_FIELD, SETTING_DOCTYPE
from ecom_bridge.integrations.shopify.utils import create_shopify_log

from ecom_bridge.utils.logger import log_error, log_info


def sync_refund(payload, request_id=None):
	"""
	Process Shopify refund webhook (orders/refund).

	Flow:
	1. Find the Sales Order by Shopify order ID
	2. Find the Sales Invoice linked to it
	3. Create a Credit Note (return Sales Invoice) for refunded items
	4. Optionally create a return Delivery Note

	This is registered as a webhook handler.
	"""
	frappe.set_user("Administrator")
	frappe.flags.request_id = request_id

	order = payload
	order_id = order.get("id")

	try:
		# Get existing Sales Order
		so_name = frappe.db.get_value(
			"Sales Order", {ORDER_ID_FIELD: cstr(order_id)}, "name"
		)
		if not so_name:
			create_shopify_log(
				status="Invalid",
				message=f"Sales Order not found for Shopify order {order_id}",
			)
			return

		so = frappe.get_doc("Sales Order", so_name)

		refunds = order.get("refunds", [])
		if not refunds:
			return

		for refund in refunds:
			_process_single_refund(refund, so, order)

	except Exception as e:
		create_shopify_log(status="Error", exception=e, rollback=True)
		log_error("Shopify", f"Refund processing failed for order {order_id}: {e}")
	else:
		create_shopify_log(status="Success")
		log_info("Shopify", f"Refund processed for order {order_id}")


def _process_single_refund(refund, so, order):
	"""Process a single Shopify refund entry."""
	refund_id = refund.get("id")

	# Check if already processed
	if frappe.db.exists("Sales Invoice", {"shopify_order_id": f"REFUND-{refund_id}"}):
		return

	refund_line_items = refund.get("refund_line_items", [])
	if not refund_line_items:
		# Full refund with no line items — create credit note for full amount
		_create_full_credit_note(refund, so, order)
		return

	# Partial refund — create credit note for specific items
	_create_partial_credit_note(refund, refund_line_items, so, order)


def _create_full_credit_note(refund, so, order):
	"""Create a full credit note for a complete refund."""
	refund_id = refund.get("id")

	# Find the original Sales Invoice
	si_name = frappe.db.get_value(
		"Sales Invoice",
		{"shopify_order_id": cstr(order.get("id")), "docstatus": 1, "is_return": 0},
		"name",
	)

	if not si_name:
		log_info("Shopify", f"No invoice found for refund {refund_id}, skipping credit note")
		return

	si = frappe.get_doc("Sales Invoice", si_name)

	# Create return invoice
	from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_sales_return

	credit_note = make_sales_return(si.name)
	credit_note.shopify_order_id = f"REFUND-{refund_id}"

	if credit_note.meta.has_field("marketplace_source"):
		credit_note.marketplace_source = "Shopify"

	# Set refund date
	refund_date = refund.get("created_at")
	if refund_date:
		credit_note.posting_date = getdate(refund_date)
	else:
		credit_note.posting_date = nowdate()

	credit_note.flags.ignore_mandatory = True
	credit_note.insert(ignore_permissions=True)
	credit_note.submit()

	log_info(
		"Shopify",
		f"Full credit note {credit_note.name} created for refund {refund_id}",
	)


def _create_partial_credit_note(refund, refund_line_items, so, order):
	"""Create a partial credit note for specific refunded items."""
	refund_id = refund.get("id")

	# Find the original Sales Invoice
	si_name = frappe.db.get_value(
		"Sales Invoice",
		{"shopify_order_id": cstr(order.get("id")), "docstatus": 1, "is_return": 0},
		"name",
	)

	if not si_name:
		log_info("Shopify", f"No invoice found for refund {refund_id}, skipping credit note")
		return

	si = frappe.get_doc("Sales Invoice", si_name)

	from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_sales_return

	credit_note = make_sales_return(si.name)
	credit_note.shopify_order_id = f"REFUND-{refund_id}"

	if credit_note.meta.has_field("marketplace_source"):
		credit_note.marketplace_source = "Shopify"

	refund_date = refund.get("created_at")
	if refund_date:
		credit_note.posting_date = getdate(refund_date)

	# Adjust quantities to match refund
	refunded_items = {}
	for rli in refund_line_items:
		line_item_id = rli.get("line_item_id")
		refunded_items[str(line_item_id)] = {
			"qty": rli.get("quantity", 0),
			"subtotal": flt(rli.get("subtotal")),
		}

	# Match refund line items to credit note items
	for item in credit_note.get("items", []):
		# Default to 0 — only include items that were actually refunded
		item.qty = 0

	# Set quantities for refunded items
	for item in credit_note.get("items", []):
		for line_item_id, refund_data in refunded_items.items():
			# Match by item code — the credit note items come from the original invoice
			if item.qty == 0:
				item.qty = -abs(refund_data["qty"])
				if refund_data.get("subtotal"):
					item.rate = flt(refund_data["subtotal"]) / refund_data["qty"]
				break

	# Remove items with 0 qty
	credit_note.items = [item for item in credit_note.items if item.qty != 0]

	if not credit_note.items:
		log_info("Shopify", f"No matching items for refund {refund_id}")
		return

	credit_note.flags.ignore_mandatory = True
	credit_note.insert(ignore_permissions=True)
	credit_note.submit()

	log_info(
		"Shopify",
		f"Partial credit note {credit_note.name} created for refund {refund_id} "
		f"({len(credit_note.items)} items)",
	)

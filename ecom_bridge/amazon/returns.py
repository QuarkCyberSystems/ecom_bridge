"""
Amazon returns and refund handling.

Processes Amazon return reports and creates Credit Notes in ERPNext.
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate

from ecom_bridge.utils.logger import log_error, log_info


def process_amazon_returns():
	"""
	Scheduled task to check for Amazon returns and create credit notes.

	Uses the SP-API Reports API to fetch return reports,
	or checks for cancelled/refunded orders.

	Runs hourly.
	"""
	from ecom_bridge.amazon.overrides import get_bridge_settings

	settings = get_bridge_settings()
	if not settings:
		return

	if not frappe.db.exists("DocType", "Amazon SP API Settings"):
		return

	amazon_settings = frappe.get_single("Amazon SP API Settings")
	if not amazon_settings.enable_sync:
		return

	# Check for Amazon orders that have been cancelled/refunded
	_process_cancelled_orders()
	_process_refunded_orders()


def _process_cancelled_orders():
	"""
	Find Amazon orders marked as Canceled and cancel corresponding ERPNext orders.
	"""
	# Find submitted Sales Orders with amazon_order_id that haven't been cancelled
	amazon_orders = frappe.db.sql(
		"""
		SELECT name, amazon_order_id
		FROM `tabSales Order`
		WHERE amazon_order_id IS NOT NULL
		AND amazon_order_id != ''
		AND docstatus = 1
		AND amazon_order_status = 'Canceled'
		AND creation > DATE_SUB(NOW(), INTERVAL 30 DAY)
		LIMIT 20
		""",
		as_dict=True,
	)

	for order in amazon_orders:
		try:
			_cancel_amazon_order(order.name, order.amazon_order_id)
		except Exception as e:
			log_error("Amazon", f"Failed to cancel order {order.name}: {e}")


def _cancel_amazon_order(so_name, amazon_order_id):
	"""Cancel a Sales Order and create credit note if invoice exists."""
	so = frappe.get_doc("Sales Order", so_name)

	# Check if SI exists
	si_name = frappe.db.get_value(
		"Sales Invoice",
		{"amazon_order_id": amazon_order_id, "docstatus": 1, "is_return": 0},
		"name",
	)

	# Check if DN exists
	dn_names = frappe.db.get_all(
		"Delivery Note Item",
		filters={"against_sales_order": so_name, "docstatus": 1},
		fields=["distinct parent as name"],
	)

	if si_name:
		# Create credit note
		_create_amazon_credit_note(si_name, amazon_order_id)
	elif not dn_names and so.docstatus == 1:
		# No invoice, no delivery — cancel the SO
		so.cancel()
		log_info("Amazon", f"Cancelled Sales Order {so_name} for Amazon order {amazon_order_id}")


def _process_refunded_orders():
	"""
	Check Amazon orders via SP-API for refund status and create credit notes.

	Uses the Orders API to check financial status of recent orders.
	"""
	from ecom_bridge.amazon.sp_api_client import get_sp_api_instance, call_sp_api_with_retry

	from ecommerce_integrations.amazon.doctype.amazon_sp_api_settings.amazon_sp_api import Orders

	orders_api = get_sp_api_instance(Orders)
	if not orders_api:
		return

	# Get recent Amazon orders that might have refunds
	recent_orders = frappe.db.sql(
		"""
		SELECT name, amazon_order_id
		FROM `tabSales Order`
		WHERE amazon_order_id IS NOT NULL
		AND amazon_order_id != ''
		AND docstatus = 1
		AND creation > DATE_SUB(NOW(), INTERVAL 14 DAY)
		AND IFNULL(amazon_order_status, '') NOT IN ('Refunded', 'Canceled')
		LIMIT 50
		""",
		as_dict=True,
	)

	if not recent_orders:
		return

	# Check each order's status via SP-API
	order_ids = [o.amazon_order_id for o in recent_orders]

	# SP-API allows checking multiple orders at once
	for batch_start in range(0, len(order_ids), 20):
		batch = order_ids[batch_start:batch_start + 20]

		result = call_sp_api_with_retry(
			orders_api.get_orders,
			max_retries=2,
			created_after="2020-01-01",  # Required param, we filter by IDs
			amazon_order_ids=batch,
		)

		if not result:
			continue

		for order_data in result.get("Orders", []):
			order_status = order_data.get("OrderStatus")
			order_id = order_data.get("AmazonOrderId")

			# Update status in ERPNext
			so_name = frappe.db.get_value(
				"Sales Order", {"amazon_order_id": order_id}, "name"
			)
			if so_name:
				frappe.db.set_value("Sales Order", so_name, "amazon_order_status", order_status)

			if order_status == "Canceled":
				if so_name:
					_cancel_amazon_order(so_name, order_id)


def _create_amazon_credit_note(si_name, amazon_order_id):
	"""Create a credit note (return invoice) for an Amazon order."""
	# Check if credit note already exists
	existing = frappe.db.exists(
		"Sales Invoice",
		{"amazon_order_id": f"RETURN-{amazon_order_id}", "is_return": 1},
	)
	if existing:
		return

	si = frappe.get_doc("Sales Invoice", si_name)

	from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_sales_return

	credit_note = make_sales_return(si.name)

	if credit_note.meta.has_field("amazon_order_id"):
		credit_note.amazon_order_id = f"RETURN-{amazon_order_id}"

	if credit_note.meta.has_field("marketplace_source"):
		credit_note.marketplace_source = "Amazon"

	credit_note.posting_date = nowdate()
	credit_note.flags.ignore_mandatory = True
	credit_note.insert(ignore_permissions=True)
	credit_note.submit()

	log_info(
		"Amazon",
		f"Credit note {credit_note.name} created for Amazon order {amazon_order_id}",
	)


@frappe.whitelist()
def manual_process_return(amazon_order_id):
	"""Manually trigger return processing for a specific Amazon order."""
	so_name = frappe.db.get_value(
		"Sales Order", {"amazon_order_id": amazon_order_id}, "name"
	)

	if not so_name:
		frappe.throw(_("Sales Order not found for Amazon order {0}").format(amazon_order_id))

	si_name = frappe.db.get_value(
		"Sales Invoice",
		{"amazon_order_id": amazon_order_id, "docstatus": 1, "is_return": 0},
		"name",
	)

	if si_name:
		_create_amazon_credit_note(si_name, amazon_order_id)
		return {"status": "success", "message": f"Credit note created for {amazon_order_id}"}
	else:
		return {"status": "skipped", "message": "No invoice found to create credit note"}

"""
Payment reconciliation for Shopify and Amazon orders.

Matches payments from marketplace payouts to Sales Invoices in ERPNext.
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate

from ecom_bridge.utils.logger import log_error, log_info


def reconcile_shopify_payments():
	"""
	Reconcile Shopify payments with Sales Invoices.

	Checks for unpaid Sales Invoices linked to Shopify orders
	that have financial_status = 'paid' and creates Payment Entries.
	"""
	from ecom_bridge.shopify.overrides import get_bridge_settings

	settings = get_bridge_settings()
	if not settings:
		return

	shopify_setting = frappe.get_single("Shopify Setting")

	# Find unpaid Shopify invoices
	unpaid_invoices = frappe.db.sql(
		"""
		SELECT si.name, si.grand_total, si.currency, si.customer,
			   si.company, si.shopify_order_id, si.outstanding_amount
		FROM `tabSales Invoice` si
		WHERE si.shopify_order_id IS NOT NULL
		AND si.shopify_order_id != ''
		AND si.shopify_order_id NOT LIKE 'REFUND-%%'
		AND si.docstatus = 1
		AND si.outstanding_amount > 0
		AND si.creation > DATE_SUB(NOW(), INTERVAL 30 DAY)
		LIMIT 50
		""",
		as_dict=True,
	)

	if not unpaid_invoices:
		return

	created = 0
	for invoice in unpaid_invoices:
		try:
			# Check if Shopify order was paid
			so = frappe.db.get_value(
				"Sales Order",
				{"shopify_order_id": invoice.shopify_order_id},
				["shopify_financial_status", "shopify_order_status"],
				as_dict=True,
			)

			if not so or so.shopify_financial_status != "paid":
				continue

			# Check if payment already exists
			existing_pe = frappe.db.exists(
				"Payment Entry Reference",
				{"reference_doctype": "Sales Invoice", "reference_name": invoice.name},
			)
			if existing_pe:
				continue

			# Create payment entry
			_create_payment_entry(
				invoice,
				shopify_setting.cash_bank_account,
				shopify_setting.company,
			)
			created += 1

		except Exception as e:
			log_error("Shopify", f"Payment reconciliation failed for {invoice.name}: {e}")

	if created:
		log_info("Shopify", f"Created {created} payment entries for Shopify invoices")


def reconcile_amazon_payments():
	"""
	Reconcile Amazon payments with Sales Invoices.

	Amazon payments come through settlement reports.
	This creates Payment Entries for submitted invoices.
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

	# Find unpaid Amazon invoices
	unpaid_invoices = frappe.db.sql(
		"""
		SELECT si.name, si.grand_total, si.currency, si.customer,
			   si.company, si.outstanding_amount
		FROM `tabSales Invoice` si
		WHERE si.amazon_order_id IS NOT NULL
		AND si.amazon_order_id != ''
		AND si.amazon_order_id NOT LIKE 'RETURN-%%'
		AND si.docstatus = 1
		AND si.outstanding_amount > 0
		AND si.creation > DATE_SUB(NOW(), INTERVAL 30 DAY)
		LIMIT 50
		""",
		as_dict=True,
	)

	if not unpaid_invoices:
		return

	# For Amazon, orders are typically prepaid
	# Get the payment account from settings or use a default
	payment_account = _get_amazon_payment_account(amazon_settings)
	if not payment_account:
		log_error("Amazon", "No payment account configured for Amazon reconciliation")
		return

	created = 0
	for invoice in unpaid_invoices:
		try:
			existing_pe = frappe.db.exists(
				"Payment Entry Reference",
				{"reference_doctype": "Sales Invoice", "reference_name": invoice.name},
			)
			if existing_pe:
				continue

			_create_payment_entry(invoice, payment_account, amazon_settings.company)
			created += 1

		except Exception as e:
			log_error("Amazon", f"Payment reconciliation failed for {invoice.name}: {e}")

	if created:
		log_info("Amazon", f"Created {created} payment entries for Amazon invoices")


def _create_payment_entry(invoice, payment_account, company):
	"""Create a Payment Entry for a Sales Invoice."""
	from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

	pe = get_payment_entry("Sales Invoice", invoice.name)
	pe.paid_amount = flt(invoice.outstanding_amount)
	pe.received_amount = flt(invoice.outstanding_amount)
	pe.paid_to = payment_account
	pe.reference_no = invoice.get("shopify_order_id") or invoice.name
	pe.reference_date = nowdate()
	pe.remarks = f"Auto-reconciled marketplace payment for {invoice.name}"

	pe.flags.ignore_mandatory = True
	pe.insert(ignore_permissions=True)
	pe.submit()

	log_info(
		"System",
		f"Payment Entry {pe.name} created for {invoice.name} "
		f"(amount: {pe.paid_amount} {invoice.currency})",
	)


def _get_amazon_payment_account(amazon_settings):
	"""Get the payment account for Amazon orders."""
	# Try to find an Amazon-specific bank account
	account = frappe.db.get_value(
		"Account",
		{
			"account_name": ["like", "%Amazon%"],
			"company": amazon_settings.company,
			"account_type": ["in", ["Bank", "Cash"]],
		},
		"name",
	)

	if account:
		return account

	# Fallback to the marketplace account group
	if amazon_settings.market_place_account_group:
		return amazon_settings.market_place_account_group

	# Final fallback — company default bank account
	return frappe.db.get_value(
		"Company", amazon_settings.company, "default_bank_account"
	)


@frappe.whitelist()
def manual_reconcile(invoice_name):
	"""Manually trigger payment reconciliation for a single invoice."""
	si = frappe.get_doc("Sales Invoice", invoice_name)

	if si.outstanding_amount <= 0:
		frappe.throw(_("Invoice {0} is already paid").format(invoice_name))

	if si.get("shopify_order_id"):
		shopify_setting = frappe.get_single("Shopify Setting")
		_create_payment_entry(si, shopify_setting.cash_bank_account, si.company)
	elif si.get("amazon_order_id"):
		amazon_settings = frappe.get_single("Amazon SP API Settings")
		payment_account = _get_amazon_payment_account(amazon_settings)
		_create_payment_entry(si, payment_account, si.company)
	else:
		frappe.throw(_("Invoice {0} is not linked to any marketplace").format(invoice_name))

	return {"status": "success", "message": f"Payment entry created for {invoice_name}"}

import frappe
from frappe import _
from frappe.utils import flt


def get_bridge_settings():
	"""Get Ecom Bridge Settings for Amazon, returns None if not configured."""
	if frappe.db.exists("DocType", "Ecom Bridge Settings"):
		settings = frappe.get_single("Ecom Bridge Settings")
		if settings.enabled and settings.enable_amazon_overrides:
			return settings
	return None


# ──────────────────────────────────────────────
# Sales Order Hooks
# ──────────────────────────────────────────────

def validate_sales_order(doc, method):
	"""Validate Amazon Sales Orders — tax, warehouse, currency checks."""
	if not doc.get("amazon_order_id"):
		return

	settings = get_bridge_settings()
	if not settings:
		return

	_validate_tax_accounts(doc)
	_validate_warehouse_mapping(doc)
	_set_marketplace_source(doc, "Amazon")

	if settings.enable_zatca_validation:
		from ecom_bridge.utils.tax import validate_zatca_on_order
		validate_zatca_on_order(doc, settings)


def on_submit_sales_order(doc, method):
	"""Post-submit processing for Amazon Sales Orders."""
	if not doc.get("amazon_order_id"):
		return

	settings = get_bridge_settings()
	if not settings:
		return

	_apply_cost_center(doc, settings.amazon_cost_center)


# ──────────────────────────────────────────────
# Sales Invoice Hooks
# ──────────────────────────────────────────────

def validate_sales_invoice(doc, method):
	"""Validate Amazon Sales Invoices — ZATCA compliance."""
	if not doc.get("amazon_order_id"):
		return

	settings = get_bridge_settings()
	if not settings:
		return

	_set_marketplace_source(doc, "Amazon")

	if settings.enable_zatca_validation:
		from ecom_bridge.utils.tax import validate_zatca_fields
		validate_zatca_fields(doc, settings)


def on_submit_sales_invoice(doc, method):
	"""Post-submit processing for Amazon invoices."""
	if not doc.get("amazon_order_id"):
		return

	settings = get_bridge_settings()
	if not settings:
		return

	_apply_cost_center(doc, settings.amazon_cost_center)


# ──────────────────────────────────────────────
# Customer Hooks
# ──────────────────────────────────────────────

def after_insert_customer(doc, method):
	"""Set defaults for Amazon customers."""
	# Amazon uses order-level customer data, not a separate customer ID field
	# Check if customer was created by Amazon integration
	if not _is_amazon_customer(doc):
		return

	settings = get_bridge_settings()
	if not settings:
		return

	if settings.amazon_default_customer_group and not doc.customer_group:
		doc.db_set("customer_group", settings.amazon_default_customer_group)

	if doc.meta.has_field("marketplace_source"):
		doc.db_set("marketplace_source", "Amazon")


# ──────────────────────────────────────────────
# Item Hooks
# ──────────────────────────────────────────────

def validate_item(doc, method):
	"""Validate items synced from Amazon."""
	from ecom_bridge.ecom_bridge.doctype.ecommerce_item import ecommerce_item

	# Check if this item is linked to Amazon
	is_amazon = frappe.db.exists(
		"Ecommerce Item",
		{"erpnext_item_code": doc.item_code, "integration": "amazon"},
	)

	if not is_amazon:
		return

	if doc.meta.has_field("marketplace_source") and not doc.marketplace_source:
		doc.marketplace_source = "Amazon"


# ──────────────────────────────────────────────
# Private Helpers
# ──────────────────────────────────────────────

def _is_amazon_customer(doc):
	"""Check if customer was created by Amazon integration."""
	# Amazon repository creates customers with specific naming pattern
	# or we can check if any Sales Order with amazon_order_id links to this customer
	return frappe.db.exists(
		"Sales Order",
		{"customer": doc.name, "amazon_order_id": ["is", "set"]},
	)


def _validate_tax_accounts(doc):
	"""Ensure all tax rows have valid account heads."""
	for tax in doc.get("taxes", []):
		if not tax.account_head:
			frappe.throw(
				_("Row {0}: Tax account head is required for Amazon order {1}").format(
					tax.idx, doc.get("amazon_order_id")
				)
			)


def _validate_warehouse_mapping(doc):
	"""Ensure all items have a warehouse assigned."""
	settings = get_bridge_settings()
	for item in doc.get("items", []):
		if not item.warehouse:
			if settings and settings.amazon_default_warehouse:
				item.warehouse = settings.amazon_default_warehouse
			else:
				frappe.throw(
					_("Row {0}: Warehouse is required for item {1} in Amazon order {2}").format(
						item.idx, item.item_code, doc.get("amazon_order_id")
					)
				)


def _set_marketplace_source(doc, source):
	"""Set the marketplace_source custom field."""
	if doc.meta.has_field("marketplace_source"):
		doc.marketplace_source = source


def _apply_cost_center(doc, cost_center):
	"""Apply cost center to all items if configured."""
	if not cost_center:
		return
	for item in doc.get("items", []):
		if not item.cost_center:
			item.db_set("cost_center", cost_center)

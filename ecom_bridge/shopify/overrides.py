import frappe
from frappe import _
from frappe.utils import flt


def get_bridge_settings():
	"""Get Ecom Bridge Settings singleton, returns None if not configured."""
	if frappe.db.exists("DocType", "Ecom Bridge Settings"):
		settings = frappe.get_single("Ecom Bridge Settings")
		if settings.enabled and settings.enable_shopify_overrides:
			return settings
	return None


# ──────────────────────────────────────────────
# Sales Order Hooks
# ──────────────────────────────────────────────

def validate_sales_order(doc, method):
	"""Validate Shopify Sales Orders — tax, warehouse, currency checks."""
	if not doc.get("shopify_order_id"):
		return

	settings = get_bridge_settings()
	if not settings:
		return

	_validate_tax_accounts(doc)
	_validate_warehouse_mapping(doc)
	_validate_currency(doc, settings)
	_set_marketplace_source(doc, "Shopify")

	if settings.enable_zatca_validation:
		from ecom_bridge.utils.tax import validate_zatca_on_order
		validate_zatca_on_order(doc, settings)


def on_submit_sales_order(doc, method):
	"""Post-submit processing for Shopify Sales Orders."""
	if not doc.get("shopify_order_id"):
		return

	settings = get_bridge_settings()
	if not settings:
		return

	_apply_cost_center(doc, settings.shopify_cost_center)


# ──────────────────────────────────────────────
# Sales Invoice Hooks
# ──────────────────────────────────────────────

def validate_sales_invoice(doc, method):
	"""Validate Shopify Sales Invoices — ZATCA compliance."""
	if not doc.get("shopify_order_id"):
		return

	settings = get_bridge_settings()
	if not settings:
		return

	_set_marketplace_source(doc, "Shopify")

	if settings.enable_zatca_validation:
		from ecom_bridge.utils.tax import validate_zatca_fields
		validate_zatca_fields(doc, settings)


def on_submit_sales_invoice(doc, method):
	"""Post-submit processing for Shopify invoices."""
	if not doc.get("shopify_order_id"):
		return

	settings = get_bridge_settings()
	if not settings:
		return

	_apply_cost_center(doc, settings.shopify_cost_center)


# ──────────────────────────────────────────────
# Delivery Note Hooks
# ──────────────────────────────────────────────

def validate_delivery_note(doc, method):
	"""Validate Shopify Delivery Notes — warehouse checks."""
	if not doc.get("shopify_order_id"):
		return

	settings = get_bridge_settings()
	if not settings:
		return

	_set_marketplace_source(doc, "Shopify")

	if settings.shopify_default_warehouse:
		for item in doc.get("items", []):
			if not item.warehouse:
				item.warehouse = settings.shopify_default_warehouse


# ──────────────────────────────────────────────
# Customer Hooks
# ──────────────────────────────────────────────

def after_insert_customer(doc, method):
	"""Set defaults for Shopify customers."""
	if not doc.get("shopify_customer_id"):
		return

	settings = get_bridge_settings()
	if not settings:
		return

	if doc.get("marketplace_source") != "Shopify":
		doc.db_set("marketplace_source", "Shopify")


# ──────────────────────────────────────────────
# Item Hooks
# ──────────────────────────────────────────────

def validate_item(doc, method):
	"""Validate items synced from Shopify."""
	if not doc.get("shopify_selling_rate"):
		return

	if flt(doc.shopify_selling_rate) < 0:
		frappe.throw(
			_("Shopify selling rate cannot be negative for item {0}").format(doc.item_code)
		)


# ──────────────────────────────────────────────
# Private Helpers
# ──────────────────────────────────────────────

def _validate_tax_accounts(doc):
	"""Ensure all tax rows have valid account heads."""
	for tax in doc.get("taxes", []):
		if not tax.account_head:
			frappe.throw(
				_("Row {0}: Tax account head is required for Shopify order {1}").format(
					tax.idx, doc.shopify_order_id
				)
			)


def _validate_warehouse_mapping(doc):
	"""Ensure all items have a warehouse assigned."""
	for item in doc.get("items", []):
		if not item.warehouse:
			frappe.throw(
				_("Row {0}: Warehouse is required for item {1} in Shopify order {2}").format(
					item.idx, item.item_code, doc.get("shopify_order_id")
				)
			)


def _validate_currency(doc, settings):
	"""Validate currency matches company default or is properly configured."""
	if not settings.default_currency:
		return

	company_currency = frappe.get_cached_value("Company", doc.company, "default_currency")
	if doc.currency and doc.currency != company_currency:
		if not frappe.db.exists("Currency Exchange", {
			"from_currency": doc.currency,
			"to_currency": company_currency,
		}):
			from ecom_bridge.utils.logger import log_warning
			log_warning(
				"Shopify",
				f"No exchange rate found for {doc.currency} → {company_currency} "
				f"on order {doc.get('shopify_order_id')}",
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

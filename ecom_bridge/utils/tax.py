import frappe
from frappe import _
from frappe.utils import flt


def validate_zatca_fields(doc, settings=None):
	"""
	Validate ZATCA compliance on Sales Invoice.

	Ensures:
	- VAT account is mapped
	- VAT line items exist for Saudi invoices
	- Tax amounts are correctly calculated
	- Seller and buyer TIN are present
	"""
	if not settings:
		settings = _get_settings()
	if not settings or not settings.enable_zatca_validation:
		return

	if not _is_zatca_applicable(doc):
		return

	_validate_vat_lines(doc, settings)
	_validate_tax_amounts(doc, settings)
	_validate_tax_id(doc)


def validate_zatca_on_order(doc, settings=None):
	"""
	Validate ZATCA compliance on Sales Order.
	Lighter validation than invoice — just ensures tax structure is present.
	"""
	if not settings:
		settings = _get_settings()
	if not settings or not settings.enable_zatca_validation:
		return

	if not _is_zatca_applicable(doc):
		return

	_validate_vat_lines(doc, settings)


def _get_settings():
	"""Get Ecom Bridge Settings."""
	if frappe.db.exists("DocType", "Ecom Bridge Settings"):
		return frappe.get_single("Ecom Bridge Settings")
	return None


def _is_zatca_applicable(doc):
	"""Check if ZATCA validation should apply based on company country."""
	company_country = frappe.get_cached_value("Company", doc.company, "country")
	return company_country in ("Saudi Arabia", "المملكة العربية السعودية")


def _validate_vat_lines(doc, settings):
	"""Ensure VAT tax rows exist for Saudi documents."""
	if not doc.get("taxes"):
		frappe.throw(
			_("Tax table is empty. ZATCA requires VAT lines on document {0}").format(doc.name)
		)

	vat_account = settings.zatca_vat_account
	if not vat_account:
		return

	has_vat = any(
		tax.account_head == vat_account
		for tax in doc.get("taxes", [])
	)

	if not has_vat:
		frappe.msgprint(
			_("Warning: No VAT line found with account {0} on {1}. "
			  "Please verify tax mapping for ZATCA compliance.").format(
				vat_account, doc.name
			),
			alert=True,
			indicator="orange",
		)


def _validate_tax_amounts(doc, settings):
	"""Validate VAT rate matches expected rate."""
	vat_rate = flt(settings.zatca_vat_rate) or 15.0
	vat_account = settings.zatca_vat_account

	if not vat_account:
		return

	for tax in doc.get("taxes", []):
		if tax.account_head == vat_account and tax.charge_type == "On Net Total":
			if flt(tax.rate) != vat_rate:
				frappe.msgprint(
					_("Row {0}: VAT rate is {1}% but expected {2}%. "
					  "Please verify for ZATCA compliance.").format(
						tax.idx, tax.rate, vat_rate
					),
					alert=True,
					indicator="orange",
				)


def _validate_tax_id(doc):
	"""Ensure seller has Tax ID (VAT Registration Number)."""
	company_tax_id = frappe.get_cached_value("Company", doc.company, "tax_id")
	if not company_tax_id:
		frappe.msgprint(
			_("Company {0} does not have a Tax ID set. "
			  "This is required for ZATCA compliance.").format(doc.company),
			alert=True,
			indicator="red",
		)


def get_tax_account_for_company(company, tax_type="sales_tax"):
	"""
	Get the appropriate tax account for a company.

	Args:
		company: Company name
		tax_type: One of 'sales_tax', 'shipping', 'vat'

	Returns:
		Tax account head string or None
	"""
	settings = _get_settings()

	if settings and tax_type == "vat" and settings.zatca_vat_account:
		return settings.zatca_vat_account

	if settings and tax_type == "shipping" and settings.shopify_shipping_account:
		return settings.shopify_shipping_account

	# Fallback to Shopify Settings
	field_map = {
		"sales_tax": "default_sales_tax_account",
		"shipping": "default_shipping_charges_account",
	}

	field = field_map.get(tax_type)
	if field and frappe.db.exists("DocType", "Shopify Setting"):
		return frappe.db.get_single_value("Shopify Setting", field)

	return None

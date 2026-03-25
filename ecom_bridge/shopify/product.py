import frappe
from frappe import _
from frappe.utils import cstr, flt


def validate_product_sync(doc, method):
	"""
	Additional validation when items are synced to/from Shopify.
	Called via doc_events on Item.
	"""
	if not doc.get("shopify_selling_rate"):
		return

	# Ensure selling rate is positive
	if flt(doc.shopify_selling_rate) < 0:
		frappe.throw(
			_("Shopify selling rate cannot be negative for item {0}").format(doc.item_code)
		)

	# Ensure item group exists
	if doc.item_group and not frappe.db.exists("Item Group", doc.item_group):
		frappe.throw(
			_("Item Group '{0}' does not exist. Please create it before syncing.").format(
				doc.item_group
			)
		)


def after_product_sync(doc, method):
	"""
	Post-sync processing for Shopify products.
	Sets marketplace source and logs the sync.
	"""
	from ecommerce_integrations.shopify.constants import MODULE_NAME

	# Check if this item has a Shopify ecommerce item link
	ecom_item = frappe.db.exists(
		"Ecommerce Item",
		{"erpnext_item_code": doc.item_code, "integration": MODULE_NAME},
	)

	if not ecom_item:
		return

	if doc.meta.has_field("marketplace_source") and not doc.marketplace_source:
		doc.db_set("marketplace_source", "Shopify")

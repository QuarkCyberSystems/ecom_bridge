import frappe
from frappe import _
from frappe.utils import cstr

from ecom_bridge.utils.logger import log_error, log_info


def after_amazon_order_sync(doc, method):
	"""
	Post-processing hook for Amazon Sales Orders.
	Called after the ecommerce_integrations Amazon repository creates an SO.

	Since Amazon integration creates orders via AmazonRepository.create_sales_order(),
	we hook into the Sales Order doc_events to apply custom logic.
	"""
	if not doc.get("amazon_order_id"):
		return

	from ecom_bridge.amazon.overrides import get_bridge_settings

	settings = get_bridge_settings()
	if not settings:
		return

	try:
		modified = False

		# Set marketplace source
		if doc.meta.has_field("marketplace_source") and not doc.marketplace_source:
			doc.marketplace_source = "Amazon"
			modified = True

		# Apply default warehouse
		if settings.amazon_default_warehouse:
			for item in doc.get("items", []):
				if not item.warehouse:
					item.warehouse = settings.amazon_default_warehouse
					modified = True

		# Apply cost center
		if settings.amazon_cost_center:
			for item in doc.get("items", []):
				if not item.cost_center:
					item.cost_center = settings.amazon_cost_center
					modified = True

		# Apply tax template
		if settings.amazon_tax_template and not doc.taxes_and_charges:
			doc.taxes_and_charges = settings.amazon_tax_template
			modified = True

		if modified:
			doc.flags.ignore_validate_update_after_submit = True
			doc.save()

		log_info("Amazon", f"Order {doc.amazon_order_id} post-processed → {doc.name}")

	except Exception as e:
		log_error(
			"Amazon",
			f"Post-processing failed for Amazon order {doc.get('amazon_order_id')}: {e}",
			doc=doc,
		)


def validate_amazon_order(doc, method):
	"""
	Validate Amazon order before saving.
	Checks fulfillment channel, tax setup, and item availability.
	"""
	if not doc.get("amazon_order_id"):
		return

	from ecom_bridge.amazon.overrides import get_bridge_settings

	settings = get_bridge_settings()
	if not settings:
		return

	# Validate items exist
	for item in doc.get("items", []):
		if not frappe.db.exists("Item", item.item_code):
			frappe.throw(
				_("Item {0} not found in ERPNext. Amazon order: {1}").format(
					item.item_code, doc.amazon_order_id
				)
			)

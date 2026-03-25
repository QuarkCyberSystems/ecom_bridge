import frappe


def setup_custom_fields():
	"""
	Create custom fields on standard DocTypes for ecom_bridge.

	First ensures base Shopify/Amazon fields exist,
	then adds ecom_bridge fields with safe insert_after targets.

	Run via:
		bench --site <site> execute ecom_bridge.shopify.custom_fields.setup_custom_fields
	"""
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	# Step 1: Ensure base Shopify/Amazon fields exist
	_ensure_ecommerce_integration_fields()

	# Step 2: Build all custom fields with safe insert_after
	custom_fields = {}
	for fields_dict in [_get_shopify_fields(), _get_amazon_fields(), _get_shared_fields()]:
		for dt, fields in fields_dict.items():
			custom_fields.setdefault(dt, []).extend(fields)

	create_custom_fields(custom_fields, update=True)
	frappe.db.commit()


def _ensure_ecommerce_integration_fields():
	"""
	Ensure base integration custom fields exist on the site.
	These are the parent fields our fields depend on.
	"""
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	# Only create if they don't already exist
	parent_fields = {}

	# Shopify fields (created by ecom_bridge)
	if not frappe.db.exists("Custom Field", {"dt": "Sales Order", "fieldname": "shopify_order_id"}):
		parent_fields.setdefault("Sales Order", []).extend([
			{
				"fieldname": "shopify_order_id",
				"label": "Shopify Order ID",
				"fieldtype": "Small Text",
				"insert_after": "column_break_44",
				"read_only": 1,
				"no_copy": 1,
			},
			{
				"fieldname": "shopify_order_number",
				"label": "Shopify Order Number",
				"fieldtype": "Small Text",
				"insert_after": "shopify_order_id",
				"read_only": 1,
				"no_copy": 1,
			},
			{
				"fieldname": "shopify_order_status",
				"label": "Shopify Order Status",
				"fieldtype": "Small Text",
				"insert_after": "shopify_order_number",
				"read_only": 1,
				"no_copy": 1,
			},
		])

	if not frappe.db.exists("Custom Field", {"dt": "Sales Order", "fieldname": "amazon_order_id"}):
		parent_fields.setdefault("Sales Order", []).append({
			"fieldname": "amazon_order_id",
			"label": "Amazon Order ID",
			"fieldtype": "Data",
			"insert_after": "shopify_order_status",
			"read_only": 1,
			"no_copy": 1,
		})

	if not frappe.db.exists("Custom Field", {"dt": "Sales Invoice", "fieldname": "shopify_order_id"}):
		parent_fields.setdefault("Sales Invoice", []).extend([
			{
				"fieldname": "shopify_order_id",
				"label": "Shopify Order ID",
				"fieldtype": "Small Text",
				"insert_after": "column_break_44",
				"read_only": 1,
				"no_copy": 1,
			},
			{
				"fieldname": "shopify_order_number",
				"label": "Shopify Order Number",
				"fieldtype": "Small Text",
				"insert_after": "shopify_order_id",
				"read_only": 1,
				"no_copy": 1,
			},
			{
				"fieldname": "shopify_order_status",
				"label": "Shopify Order Status",
				"fieldtype": "Small Text",
				"insert_after": "shopify_order_number",
				"read_only": 1,
				"no_copy": 1,
			},
		])

	if not frappe.db.exists("Custom Field", {"dt": "Delivery Note", "fieldname": "shopify_order_id"}):
		parent_fields.setdefault("Delivery Note", []).extend([
			{
				"fieldname": "shopify_order_id",
				"label": "Shopify Order ID",
				"fieldtype": "Small Text",
				"insert_after": "column_break_44",
				"read_only": 1,
				"no_copy": 1,
			},
			{
				"fieldname": "shopify_fulfillment_id",
				"label": "Shopify Fulfillment ID",
				"fieldtype": "Small Text",
				"insert_after": "shopify_order_id",
				"read_only": 1,
				"no_copy": 1,
			},
		])

	if not frappe.db.exists("Custom Field", {"dt": "Customer", "fieldname": "shopify_customer_id"}):
		parent_fields.setdefault("Customer", []).append({
			"fieldname": "shopify_customer_id",
			"label": "Shopify Customer ID",
			"fieldtype": "Data",
			"insert_after": "customer_type",
			"read_only": 1,
			"no_copy": 1,
		})

	if not frappe.db.exists("Custom Field", {"dt": "Item", "fieldname": "shopify_selling_rate"}):
		parent_fields.setdefault("Item", []).append({
			"fieldname": "shopify_selling_rate",
			"label": "Shopify Selling Rate",
			"fieldtype": "Currency",
			"insert_after": "standard_rate",
			"read_only": 1,
			"no_copy": 1,
		})

	if parent_fields:
		create_custom_fields(parent_fields, update=True)
		frappe.db.commit()


def _get_shopify_fields():
	"""Shopify-specific custom fields."""
	return {
		"Sales Order": [
			{
				"fieldname": "shopify_tags",
				"label": "Shopify Tags",
				"fieldtype": "Small Text",
				"insert_after": "shopify_order_status",
				"read_only": 1,
				"no_copy": 1,
				"module": "Ecom Bridge",
			},
			{
				"fieldname": "shopify_notes",
				"label": "Shopify Notes",
				"fieldtype": "Small Text",
				"insert_after": "shopify_tags",
				"read_only": 1,
				"no_copy": 1,
				"module": "Ecom Bridge",
			},
			{
				"fieldname": "shopify_financial_status",
				"label": "Shopify Financial Status",
				"fieldtype": "Data",
				"insert_after": "shopify_notes",
				"read_only": 1,
				"no_copy": 1,
				"module": "Ecom Bridge",
			},
			{
				"fieldname": "shopify_fulfillment_status",
				"label": "Shopify Fulfillment Status",
				"fieldtype": "Data",
				"insert_after": "shopify_financial_status",
				"read_only": 1,
				"no_copy": 1,
				"module": "Ecom Bridge",
			},
		],
	}


def _get_amazon_fields():
	"""Amazon-specific custom fields."""
	return {
		"Sales Order": [
			{
				"fieldname": "amazon_fulfillment_channel",
				"label": "Amazon Fulfillment Channel",
				"fieldtype": "Data",
				"insert_after": "amazon_order_id",
				"read_only": 1,
				"no_copy": 1,
				"module": "Ecom Bridge",
			},
			{
				"fieldname": "amazon_order_status",
				"label": "Amazon Order Status",
				"fieldtype": "Data",
				"insert_after": "amazon_fulfillment_channel",
				"read_only": 1,
				"no_copy": 1,
				"module": "Ecom Bridge",
			},
		],
		"Sales Invoice": [
			{
				"fieldname": "amazon_order_id",
				"label": "Amazon Order ID",
				"fieldtype": "Data",
				"insert_after": "shopify_order_status",
				"read_only": 1,
				"no_copy": 1,
				"module": "Ecom Bridge",
			},
		],
		"Delivery Note": [
			{
				"fieldname": "amazon_order_id",
				"label": "Amazon Order ID",
				"fieldtype": "Data",
				"insert_after": "shopify_fulfillment_id",
				"read_only": 1,
				"no_copy": 1,
				"module": "Ecom Bridge",
			},
		],
	}


def _get_shared_fields():
	"""Shared fields across both platforms."""
	return {
		"Sales Order": [
			{
				"fieldname": "ecom_bridge_section",
				"label": "Ecom Bridge",
				"fieldtype": "Section Break",
				"insert_after": "amazon_order_status",
				"collapsible": 1,
				"module": "Ecom Bridge",
			},
			{
				"fieldname": "marketplace_source",
				"label": "Marketplace Source",
				"fieldtype": "Select",
				"options": "\nShopify\nAmazon",
				"insert_after": "ecom_bridge_section",
				"read_only": 1,
				"in_list_view": 1,
				"in_standard_filter": 1,
				"module": "Ecom Bridge",
			},
		],
		"Sales Invoice": [
			{
				"fieldname": "marketplace_source",
				"label": "Marketplace Source",
				"fieldtype": "Select",
				"options": "\nShopify\nAmazon",
				"insert_after": "amazon_order_id",
				"read_only": 1,
				"in_list_view": 1,
				"in_standard_filter": 1,
				"module": "Ecom Bridge",
			},
		],
		"Customer": [
			{
				"fieldname": "marketplace_source",
				"label": "Marketplace Source",
				"fieldtype": "Select",
				"options": "\nShopify\nAmazon",
				"insert_after": "shopify_customer_id",
				"read_only": 1,
				"in_standard_filter": 1,
				"module": "Ecom Bridge",
			},
		],
		"Item": [
			{
				"fieldname": "marketplace_source",
				"label": "Marketplace Source",
				"fieldtype": "Select",
				"options": "\nShopify\nAmazon",
				"insert_after": "shopify_selling_rate",
				"read_only": 1,
				"in_standard_filter": 1,
				"module": "Ecom Bridge",
			},
		],
		"Delivery Note": [
			{
				"fieldname": "marketplace_source",
				"label": "Marketplace Source",
				"fieldtype": "Select",
				"options": "\nShopify\nAmazon",
				"insert_after": "amazon_order_id",
				"read_only": 1,
				"in_standard_filter": 1,
				"module": "Ecom Bridge",
			},
		],
	}

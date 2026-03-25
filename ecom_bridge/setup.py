import frappe


def after_install():
	"""Run after app installation — create custom fields."""
	from ecom_bridge.shopify.custom_fields import setup_custom_fields
	setup_custom_fields()
	frappe.msgprint("Ecom Bridge: Custom fields created successfully")


def after_migrate():
	"""Run after bench migrate — ensure custom fields are up to date."""
	from ecom_bridge.shopify.custom_fields import setup_custom_fields
	setup_custom_fields()

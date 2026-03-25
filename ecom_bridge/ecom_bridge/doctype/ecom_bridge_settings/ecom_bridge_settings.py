import frappe
from frappe.model.document import Document


class EcomBridgeSettings(Document):

	def validate(self):
		if self.enable_zatca_validation and not self.zatca_vat_account:
			frappe.throw("VAT Account is required when ZATCA Validation is enabled")

		if self.enable_error_notifications and not self.notification_email:
			frappe.throw("Notification Email is required when Error Notifications are enabled")

		if self.log_retention_days and self.log_retention_days < 7:
			frappe.throw("Log Retention must be at least 7 days")

	def is_shopify_enabled(self):
		return self.enabled and self.enable_shopify_overrides

	def is_amazon_enabled(self):
		return self.enabled and self.enable_amazon_overrides

	def get_shopify_warehouse(self):
		return self.shopify_default_warehouse or frappe.db.get_single_value(
			"Shopify Setting", "warehouse"
		)

	def get_amazon_warehouse(self):
		return self.amazon_default_warehouse or frappe.db.get_single_value(
			"Amazon SP API Settings", "warehouse"
		)

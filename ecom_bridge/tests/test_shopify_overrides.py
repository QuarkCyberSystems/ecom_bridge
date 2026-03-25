"""Tests for Shopify overrides in ecom_bridge."""

import frappe
from frappe.tests import IntegrationTestCase


class TestShopifyOverrides(IntegrationTestCase):

	def setUp(self):
		self._ensure_settings()

	def _ensure_settings(self):
		"""Ensure Ecom Bridge Settings exists for tests."""
		if not frappe.db.exists("Ecom Bridge Settings"):
			settings = frappe.new_doc("Ecom Bridge Settings")
			settings.enabled = 1
			settings.company = frappe.db.get_single_value("Global Defaults", "default_company")
			settings.enable_shopify_overrides = 1
			settings.enable_amazon_overrides = 1
			settings.log_retention_days = 30
			settings.flags.ignore_mandatory = True
			settings.save()

	def test_get_bridge_settings(self):
		"""Test that bridge settings can be retrieved."""
		from ecom_bridge.shopify.overrides import get_bridge_settings

		settings = get_bridge_settings()
		self.assertIsNotNone(settings)
		self.assertTrue(settings.enabled)

	def test_validate_sales_order_skips_non_shopify(self):
		"""Test that non-Shopify orders are not validated."""
		from ecom_bridge.shopify.overrides import validate_sales_order

		doc = frappe.new_doc("Sales Order")
		# No shopify_order_id — should skip without error
		validate_sales_order(doc, "validate")

	def test_marketplace_source_field_exists(self):
		"""Test that marketplace_source custom field was created."""
		meta = frappe.get_meta("Sales Order")
		self.assertTrue(meta.has_field("marketplace_source"))

	def test_shopify_custom_fields_exist(self):
		"""Test that Shopify custom fields exist on Sales Order."""
		meta = frappe.get_meta("Sales Order")
		expected_fields = [
			"shopify_order_id",
			"shopify_tags",
			"shopify_notes",
			"shopify_financial_status",
			"shopify_fulfillment_status",
		]
		for field in expected_fields:
			self.assertTrue(
				meta.has_field(field),
				f"Expected custom field '{field}' on Sales Order",
			)

	def test_amazon_custom_fields_exist(self):
		"""Test that Amazon custom fields exist on Sales Order."""
		meta = frappe.get_meta("Sales Order")
		expected_fields = [
			"amazon_order_id",
			"amazon_fulfillment_channel",
			"amazon_order_status",
		]
		for field in expected_fields:
			self.assertTrue(
				meta.has_field(field),
				f"Expected custom field '{field}' on Sales Order",
			)

	def test_marketplace_source_on_multiple_doctypes(self):
		"""Test marketplace_source exists on all required DocTypes."""
		doctypes = ["Sales Order", "Sales Invoice", "Customer", "Item", "Delivery Note"]
		for dt in doctypes:
			meta = frappe.get_meta(dt)
			self.assertTrue(
				meta.has_field("marketplace_source"),
				f"Expected 'marketplace_source' field on {dt}",
			)


class TestZATCAValidation(IntegrationTestCase):

	def test_zatca_not_applicable_for_non_saudi(self):
		"""Test ZATCA validation skips non-Saudi companies."""
		from ecom_bridge.utils.tax import _is_zatca_applicable

		doc = frappe.new_doc("Sales Order")
		doc.company = frappe.db.get_single_value("Global Defaults", "default_company")

		# Only applicable if company country is Saudi Arabia
		result = _is_zatca_applicable(doc)
		company_country = frappe.get_cached_value("Company", doc.company, "country")

		if company_country in ("Saudi Arabia", "المملكة العربية السعودية"):
			self.assertTrue(result)
		else:
			self.assertFalse(result)


class TestLogger(IntegrationTestCase):

	def test_log_info(self):
		"""Test that log_info creates a log entry."""
		from ecom_bridge.utils.logger import log_info

		# Should not raise
		log_info("Shopify", "Test log message from unit test")

	def test_log_error(self):
		"""Test that log_error creates a log entry."""
		from ecom_bridge.utils.logger import log_error

		# Should not raise
		log_error("Amazon", "Test error message from unit test")


class TestCurrency(IntegrationTestCase):

	def test_same_currency_returns_one(self):
		"""Test same currency exchange rate is 1.0."""
		from ecom_bridge.utils.currency import get_exchange_rate

		rate = get_exchange_rate("USD", "USD")
		self.assertEqual(rate, 1.0)

	def test_unknown_currency_returns_none(self):
		"""Test unknown currency pair returns None."""
		from ecom_bridge.utils.currency import get_exchange_rate

		rate = get_exchange_rate("XYZ", "ABC")
		self.assertIsNone(rate)


class TestRetry(IntegrationTestCase):

	def test_retry_decorator_succeeds(self):
		"""Test retry decorator with successful function."""
		from ecom_bridge.utils.retry import retry_on_failure

		call_count = {"value": 0}

		@retry_on_failure(max_retries=3, base_delay=0.01)
		def always_succeeds():
			call_count["value"] += 1
			return "success"

		result = always_succeeds()
		self.assertEqual(result, "success")
		self.assertEqual(call_count["value"], 1)

	def test_retry_decorator_retries_then_succeeds(self):
		"""Test retry decorator retries on failure then succeeds."""
		from ecom_bridge.utils.retry import retry_on_failure

		call_count = {"value": 0}

		@retry_on_failure(max_retries=3, base_delay=0.01)
		def fails_twice():
			call_count["value"] += 1
			if call_count["value"] < 3:
				raise ValueError("Not yet")
			return "success"

		result = fails_twice()
		self.assertEqual(result, "success")
		self.assertEqual(call_count["value"], 3)

	def test_retry_decorator_exhausts_retries(self):
		"""Test retry decorator raises after max retries."""
		from ecom_bridge.utils.retry import retry_on_failure

		@retry_on_failure(max_retries=2, base_delay=0.01)
		def always_fails():
			raise ValueError("Always fails")

		with self.assertRaises(ValueError):
			always_fails()


class TestDashboardAPI(IntegrationTestCase):

	def test_get_sync_dashboard(self):
		"""Test dashboard API returns expected structure."""
		from ecom_bridge.api.dashboard import get_sync_dashboard

		result = get_sync_dashboard()
		self.assertIn("shopify", result)
		self.assertIn("amazon", result)
		self.assertIn("summary", result)
		self.assertIn("recent_errors", result)

	def test_get_sync_logs(self):
		"""Test sync logs API returns list."""
		from ecom_bridge.api.dashboard import get_sync_logs

		result = get_sync_logs()
		self.assertIsInstance(result, list)

	def test_force_sync_invalid_integration(self):
		"""Test force sync with invalid integration throws error."""
		from ecom_bridge.api.dashboard import force_sync

		with self.assertRaises(Exception):
			force_sync("invalid_platform")

"""
Amazon SP-API client extensions for ecom_bridge.

Adds Feeds API and Fulfillment API to the existing SPAPI base class
from ecommerce_integrations.
"""

import json
import time

import frappe
from frappe import _

from ecommerce_integrations.amazon.doctype.amazon_sp_api_settings.amazon_sp_api import (
	SPAPI,
	SPAPIError,
)

from ecom_bridge.utils.logger import log_error, log_info


class Feeds(SPAPI):
	"""Amazon SP-API Feeds API — used for inventory and price updates."""

	BASE_URI = "/feeds/2021-06-30/"

	def create_feed(self, feed_type, marketplace_ids, content, content_type="application/json"):
		"""
		Create a feed document for Amazon.

		Args:
			feed_type: e.g. 'JSON_LISTINGS_FEED', 'POST_INVENTORY_AVAILABILITY_DATA'
			marketplace_ids: List of marketplace IDs
			content: Feed content (dict or string)
			content_type: MIME type
		"""
		# Step 1: Create feed document
		data = json.dumps({
			"feedType": feed_type,
			"marketplaceIds": marketplace_ids,
			"inputFeedDocumentId": self._create_feed_document(content_type, content),
		})

		return self.make_request(
			method="POST",
			append_to_base_uri="feeds",
			data=data,
		)

	def _create_feed_document(self, content_type, content):
		"""Create a feed document and upload content."""
		data = json.dumps({"contentType": content_type})

		response = self.make_request(
			method="POST",
			append_to_base_uri="documents",
			data=data,
		)

		payload = response.get("payload", response)
		feed_document_id = payload.get("feedDocumentId")
		upload_url = payload.get("url")

		if upload_url and content:
			from requests import request as http_request

			if isinstance(content, dict):
				content = json.dumps(content)

			http_request(
				method="PUT",
				url=upload_url,
				data=content.encode("utf-8") if isinstance(content, str) else content,
				headers={"Content-Type": content_type},
			)

		return feed_document_id

	def get_feed(self, feed_id):
		"""Get feed processing status."""
		return self.make_request(append_to_base_uri=f"feeds/{feed_id}")

	def get_feed_document(self, feed_document_id):
		"""Get feed document (results)."""
		return self.make_request(append_to_base_uri=f"documents/{feed_document_id}")


class Fulfillment(SPAPI):
	"""Amazon SP-API Fulfillment — for confirming shipments on MFN orders."""

	BASE_URI = "/orders/v0/orders"

	def update_shipment_status(self, order_id, tracking_number="", carrier=""):
		"""
		Confirm shipment for a Merchant Fulfilled Network (MFN) order.

		Uses the Orders API to update fulfillment status.
		"""
		data = json.dumps({
			"marketplaceId": self.marketplace_id,
			"shipmentStatus": "ReadyForPickup",
			"orderItems": [],  # Empty means all items
			"trackingNumber": tracking_number,
			"carrierCode": carrier,
		})

		return self.make_request(
			method="POST",
			append_to_base_uri=f"/{order_id}/shipment",
			data=data,
		)


class InventoryAPI(SPAPI):
	"""Amazon SP-API Inventory — for FBA inventory queries."""

	BASE_URI = "/fba/inventory/v1/"

	def get_inventory_summaries(self, marketplace_id=None, granularity_type="Marketplace",
								next_token=None, seller_skus=None):
		"""Get FBA inventory summary."""
		if not marketplace_id:
			marketplace_id = self.marketplace_id

		params = {
			"details": "true",
			"granularityType": granularity_type,
			"granularityId": marketplace_id,
			"marketplaceIds": marketplace_id,
		}

		if next_token:
			params["nextToken"] = next_token
		if seller_skus:
			params["sellerSkus"] = ",".join(seller_skus)

		return self.make_request(
			append_to_base_uri="summaries",
			params=params,
		)


def get_sp_api_instance(cls):
	"""
	Create an SP-API instance from Amazon SP API Settings.

	Args:
		cls: The SPAPI subclass to instantiate (Feeds, Fulfillment, InventoryAPI)

	Returns:
		Instance of the specified class, or None if settings not configured.
	"""
	if not frappe.db.exists("DocType", "Amazon SP API Settings"):
		return None

	amz_setting = frappe.get_single("Amazon SP API Settings")
	if not amz_setting.enable_sync:
		return None

	return cls(
		iam_arn=amz_setting.iam_arn,
		client_id=amz_setting.client_id,
		client_secret=amz_setting.get_password("client_secret"),
		refresh_token=amz_setting.refresh_token,
		aws_access_key=amz_setting.aws_access_key,
		aws_secret_key=amz_setting.get_password("aws_secret_key"),
		country_code=amz_setting.country,
	)


def call_sp_api_with_retry(sp_api_method, max_retries=3, **kwargs):
	"""
	Call an SP-API method with retry logic and exponential backoff.

	Args:
		sp_api_method: The API method to call
		max_retries: Maximum retry attempts
		**kwargs: Arguments to pass to the API method

	Returns:
		API response payload, or None on failure
	"""
	errors = {}

	for attempt in range(max_retries):
		try:
			result = sp_api_method(**kwargs)
			return result.get("payload", result)
		except SPAPIError as e:
			errors[e.error] = e.error_description
			wait_time = min(2 ** attempt, 30)  # Exponential backoff, max 30s
			log_info(
				"Amazon",
				f"SP-API retry {attempt + 1}/{max_retries} for {sp_api_method.__name__}, "
				f"waiting {wait_time}s. Error: {e.error}",
			)
			time.sleep(wait_time)
		except Exception as e:
			log_error("Amazon", f"SP-API unexpected error: {e}")
			break

	# All retries exhausted
	for error, desc in errors.items():
		log_error("Amazon", f"SP-API failed after {max_retries} retries: {error} — {desc}")

	return None

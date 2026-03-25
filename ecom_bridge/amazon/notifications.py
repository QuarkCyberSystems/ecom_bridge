"""
Amazon SQS/SNS notification listener.

Amazon SP-API uses SQS queues for event notifications (order status changes,
listing updates, etc.) instead of webhooks.

This module polls an SQS queue for Amazon events and processes them.
"""

import json

import frappe
from frappe import _

from ecom_bridge.utils.logger import log_error, log_info


def poll_amazon_notifications():
	"""
	Poll Amazon SQS queue for notifications.

	Scheduled to run every 5 minutes.

	Setup:
	1. Create SQS queue in AWS
	2. Subscribe to Amazon SP-API notifications (e.g., ORDER_CHANGE, LISTINGS_ITEM_MFN_QUANTITY_CHANGE)
	3. Configure queue URL in Ecom Bridge Settings

	Uses boto3 to read messages from SQS.
	"""
	from ecom_bridge.amazon.overrides import get_bridge_settings

	settings = get_bridge_settings()
	if not settings:
		return

	if not frappe.db.exists("DocType", "Amazon SP API Settings"):
		return

	amazon_settings = frappe.get_single("Amazon SP API Settings")
	if not amazon_settings.enable_sync:
		return

	# Get SQS queue URL from settings
	sqs_queue_url = _get_sqs_queue_url(settings)
	if not sqs_queue_url:
		return

	try:
		import boto3

		sqs_client = boto3.client(
			"sqs",
			aws_access_key_id=amazon_settings.aws_access_key,
			aws_secret_access_key=amazon_settings.get_password("aws_secret_key"),
			region_name=_get_aws_region(amazon_settings.country),
		)

		# Receive messages (long polling, max 10)
		response = sqs_client.receive_message(
			QueueUrl=sqs_queue_url,
			MaxNumberOfMessages=10,
			WaitTimeSeconds=5,
			MessageAttributeNames=["All"],
		)

		messages = response.get("Messages", [])
		if not messages:
			return

		processed = 0
		for message in messages:
			try:
				_process_sqs_message(message, sqs_client, sqs_queue_url)
				processed += 1
			except Exception as e:
				log_error("Amazon", f"Failed to process SQS message: {e}")

		if processed:
			log_info("Amazon", f"Processed {processed} SQS notifications")

	except ImportError:
		log_error("Amazon", "boto3 is required for SQS notifications. Install with: pip install boto3")
	except Exception as e:
		log_error("Amazon", f"SQS polling failed: {e}", exception=e)


def _process_sqs_message(message, sqs_client, queue_url):
	"""Process a single SQS message from Amazon."""
	body = json.loads(message.get("Body", "{}"))
	receipt_handle = message.get("ReceiptHandle")

	# SNS wraps the actual notification
	if "Message" in body:
		notification = json.loads(body["Message"])
	else:
		notification = body

	notification_type = notification.get("NotificationType", "")

	# Route to appropriate handler
	handlers = {
		"ORDER_CHANGE": _handle_order_change,
		"LISTINGS_ITEM_MFN_QUANTITY_CHANGE": _handle_inventory_change,
		"REPORT_PROCESSING_FINISHED": _handle_report_ready,
		"FEED_PROCESSING_FINISHED": _handle_feed_complete,
	}

	handler = handlers.get(notification_type)
	if handler:
		handler(notification)
	else:
		log_info("Amazon", f"Unhandled notification type: {notification_type}")

	# Delete message from queue after processing
	sqs_client.delete_message(
		QueueUrl=queue_url,
		ReceiptHandle=receipt_handle,
	)


def _handle_order_change(notification):
	"""Handle ORDER_CHANGE notification — update order status in ERPNext."""
	payload = notification.get("Payload", {})
	order_change = payload.get("OrderChangeNotification", {})

	amazon_order_id = order_change.get("AmazonOrderId")
	new_status = order_change.get("OrderStatus")

	if not amazon_order_id:
		return

	so_name = frappe.db.get_value(
		"Sales Order", {"amazon_order_id": amazon_order_id}, "name"
	)

	if not so_name:
		log_info("Amazon", f"Order {amazon_order_id} not found in ERPNext, skipping status update")
		return

	# Update order status
	if frappe.db.has_column("Sales Order", "amazon_order_status"):
		frappe.db.set_value("Sales Order", so_name, "amazon_order_status", new_status)

	# Handle cancellations
	if new_status == "Canceled":
		from ecom_bridge.amazon.returns import _cancel_amazon_order
		try:
			_cancel_amazon_order(so_name, amazon_order_id)
		except Exception as e:
			log_error("Amazon", f"Auto-cancel failed for {amazon_order_id}: {e}")

	log_info("Amazon", f"Order {amazon_order_id} status updated to {new_status}")


def _handle_inventory_change(notification):
	"""Handle inventory change notification."""
	payload = notification.get("Payload", {})
	log_info(
		"Amazon",
		f"Inventory change notification received: {json.dumps(payload)[:500]}",
	)


def _handle_report_ready(notification):
	"""Handle report processing finished notification."""
	payload = notification.get("Payload", {})
	report_id = payload.get("ReportId", "")
	log_info("Amazon", f"Report ready: {report_id}")


def _handle_feed_complete(notification):
	"""Handle feed processing finished notification."""
	payload = notification.get("Payload", {})
	feed_id = payload.get("FeedId", "")
	processing_status = payload.get("ProcessingStatus", "")

	if processing_status == "DONE":
		log_info("Amazon", f"Feed {feed_id} completed successfully")
	else:
		log_error("Amazon", f"Feed {feed_id} finished with status: {processing_status}")


def _get_sqs_queue_url(settings):
	"""Get SQS queue URL from Ecom Bridge Settings."""
	if hasattr(settings, "amazon_sqs_queue_url") and settings.amazon_sqs_queue_url:
		return settings.amazon_sqs_queue_url
	return None


def _get_aws_region(country_code):
	"""Map Amazon country code to AWS region."""
	from ecom_bridge.ecom_bridge.doctype.amazon_sp_api_settings.amazon_sp_api import (
		Util,
	)

	try:
		marketplace = Util.get_marketplace(country_code)
		return marketplace.get("AWS Region", "us-east-1")
	except KeyError:
		return "us-east-1"

import frappe
from frappe.utils import add_days, now_datetime, nowdate

from ecom_bridge.utils.logger import log_error, log_info


def daily_sync_cleanup():
	"""Daily cleanup of old sync logs."""
	if not frappe.db.exists("DocType", "Ecom Bridge Settings"):
		return

	settings = frappe.get_single("Ecom Bridge Settings")
	if not settings.enabled:
		return

	days_to_keep = settings.log_retention_days or 30
	cutoff_date = add_days(nowdate(), -days_to_keep)

	deleted = frappe.db.delete(
		"Ecommerce Integration Log",
		filters={"creation": ("<", cutoff_date), "status": "Success"},
	)

	if deleted:
		frappe.db.commit()
		log_info("System", f"Cleaned up sync logs older than {days_to_keep} days")


def sync_health_check():
	"""
	Hourly health check — verify integrations are running.
	Sends notification if last sync was too long ago.
	"""
	if not frappe.db.exists("DocType", "Ecom Bridge Settings"):
		return

	settings = frappe.get_single("Ecom Bridge Settings")
	if not settings.enabled or not settings.enable_error_notifications:
		return

	_check_shopify_sync_health(settings)
	_check_amazon_sync_health(settings)


def _check_shopify_sync_health(settings):
	"""Check if Shopify sync is healthy."""
	if not settings.enable_shopify_overrides:
		return

	last_log = frappe.db.get_value(
		"Ecommerce Integration Log",
		filters={"integration": "shopify"},
		fieldname="creation",
		order_by="creation desc",
	)

	if not last_log:
		return

	from frappe.utils import time_diff_in_hours
	hours_since = time_diff_in_hours(now_datetime(), last_log)

	if hours_since > 6:
		_send_alert(
			settings,
			f"Shopify sync may be stalled — last log was {int(hours_since)} hours ago",
		)


def _check_amazon_sync_health(settings):
	"""Check if Amazon sync is healthy."""
	if not settings.enable_amazon_overrides:
		return

	last_log = frappe.db.get_value(
		"Ecommerce Integration Log",
		filters={"integration": "amazon"},
		fieldname="creation",
		order_by="creation desc",
	)

	if not last_log:
		return

	from frappe.utils import time_diff_in_hours
	hours_since = time_diff_in_hours(now_datetime(), last_log)

	if hours_since > 6:
		_send_alert(
			settings,
			f"Amazon sync may be stalled — last log was {int(hours_since)} hours ago",
		)


def _send_alert(settings, message):
	"""Send email notification for sync issues."""
	if not settings.notification_email:
		return

	try:
		frappe.sendmail(
			recipients=[settings.notification_email],
			subject=f"Ecom Bridge Alert — {frappe.local.site}",
			message=message,
			now=True,
		)
	except Exception:
		log_error("System", f"Failed to send alert email: {message}")

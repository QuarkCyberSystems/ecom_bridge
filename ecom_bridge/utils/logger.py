import frappe
from frappe.utils import now_datetime


def log_info(integration, message, doc=None):
	"""Log an info-level message for ecom bridge operations."""
	_create_log("Success", integration, message, doc)


def log_warning(integration, message, doc=None):
	"""Log a warning-level message."""
	_create_log("Skipped", integration, message, doc)


def log_error(integration, message, doc=None, exception=None):
	"""Log an error-level message and optionally send notification."""
	_create_log("Error", integration, message, doc)

	if exception:
		frappe.log_error(
			title=f"Ecom Bridge - {integration}",
			message=f"{message}\n\n{exception}",
		)

	# Send notification if configured
	_notify_on_error(integration, message)


def _create_log(status, integration, message, doc=None):
	"""Create an Ecommerce Integration Log entry."""
	try:
		if not frappe.db.exists("DocType", "Ecommerce Integration Log"):
			# Fallback to Error Log if ecommerce_integrations log not available
			frappe.log_error(
				title=f"Ecom Bridge [{integration}] - {status}",
				message=message,
			)
			return

		log = frappe.new_doc("Ecommerce Integration Log")
		log.integration = integration.lower()
		log.status = status
		log.message = message[:5000] if message else ""
		log.method = f"ecom_bridge.{integration.lower()}"

		if doc:
			log.reference_doctype = doc.doctype
			log.reference_name = doc.name

		log.flags.ignore_permissions = True
		log.insert()
		frappe.db.commit()

	except Exception:
		# Never let logging break the actual operation
		pass


def _notify_on_error(integration, message):
	"""Send email notification on error if configured."""
	try:
		if not frappe.db.exists("DocType", "Ecom Bridge Settings"):
			return

		settings = frappe.get_single("Ecom Bridge Settings")
		if not settings.enable_error_notifications or not settings.notification_email:
			return

		if integration.lower() == "shopify" and not settings.notify_on_order_sync_failure:
			return
		if integration.lower() == "amazon" and not settings.notify_on_order_sync_failure:
			return

		frappe.sendmail(
			recipients=[settings.notification_email],
			subject=f"Ecom Bridge Error — {integration} — {frappe.local.site}",
			message=f"<p><strong>{integration} Error</strong></p><p>{message}</p>"
			f"<p>Time: {now_datetime()}</p>"
			f"<p>Site: {frappe.local.site}</p>",
			now=True,
		)
	except Exception:
		pass

"""
Retry mechanism with exponential backoff for ecom_bridge operations.

Provides decorators and utilities for retrying failed API calls
and sync operations.
"""

import functools
import time

import frappe

from ecom_bridge.utils.logger import log_error, log_info


def retry_on_failure(max_retries=3, base_delay=1, max_delay=60, exceptions=(Exception,)):
	"""
	Decorator that retries a function on failure with exponential backoff.

	Args:
		max_retries: Maximum number of retry attempts
		base_delay: Initial delay in seconds
		max_delay: Maximum delay in seconds
		exceptions: Tuple of exception types to catch

	Usage:
		@retry_on_failure(max_retries=3, base_delay=2)
		def sync_order(order_id):
			...
	"""
	def decorator(func):
		@functools.wraps(func)
		def wrapper(*args, **kwargs):
			last_exception = None

			for attempt in range(max_retries + 1):
				try:
					return func(*args, **kwargs)
				except exceptions as e:
					last_exception = e
					if attempt < max_retries:
						delay = min(base_delay * (2 ** attempt), max_delay)
						log_info(
							"System",
							f"Retry {attempt + 1}/{max_retries} for {func.__name__}, "
							f"waiting {delay}s. Error: {e}",
						)
						time.sleep(delay)
					else:
						log_error(
							"System",
							f"{func.__name__} failed after {max_retries} retries: {e}",
						)

			raise last_exception

		return wrapper
	return decorator


def enqueue_with_retry(method, queue="short", max_retries=3, timeout=300, **kwargs):
	"""
	Enqueue a background job with retry logic built in.

	If the job fails, it will be re-enqueued with exponential backoff.

	Args:
		method: Dotted path to the method
		queue: RQ queue name
		max_retries: Maximum retry attempts
		timeout: Job timeout in seconds
		**kwargs: Arguments to pass to the method
	"""
	frappe.enqueue(
		"ecom_bridge.utils.retry._execute_with_retry",
		queue=queue,
		timeout=timeout,
		method=method,
		max_retries=max_retries,
		attempt=0,
		method_kwargs=kwargs,
	)


def _execute_with_retry(method, max_retries, attempt, method_kwargs):
	"""Execute a method with retry logic (called as background job)."""
	try:
		func = frappe.get_attr(method)
		func(**method_kwargs)
	except Exception as e:
		if attempt < max_retries:
			delay = min(2 ** attempt, 60)
			log_info(
				"System",
				f"Background job retry {attempt + 1}/{max_retries} for {method}, "
				f"scheduling in {delay}s",
			)
			# Re-enqueue with incremented attempt
			frappe.enqueue(
				"ecom_bridge.utils.retry._execute_with_retry",
				queue="short",
				timeout=300,
				enqueue_after_commit=True,
				method=method,
				max_retries=max_retries,
				attempt=attempt + 1,
				method_kwargs=method_kwargs,
			)
		else:
			log_error(
				"System",
				f"Background job {method} failed after {max_retries} retries: {e}",
				exception=e,
			)
			raise

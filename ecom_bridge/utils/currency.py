import frappe
from frappe import _
from frappe.utils import flt


def get_exchange_rate(from_currency, to_currency, date=None):
	"""
	Get currency exchange rate.
	Checks Currency Exchange table, falls back to 1.0 for same currency.
	"""
	if from_currency == to_currency:
		return 1.0

	if not date:
		from frappe.utils import nowdate
		date = nowdate()

	# Try exact date match first
	rate = frappe.db.get_value(
		"Currency Exchange",
		filters={
			"from_currency": from_currency,
			"to_currency": to_currency,
			"date": ("<=", date),
		},
		fieldname="exchange_rate",
		order_by="date desc",
	)

	if rate:
		return flt(rate)

	# Try reverse
	reverse_rate = frappe.db.get_value(
		"Currency Exchange",
		filters={
			"from_currency": to_currency,
			"to_currency": from_currency,
			"date": ("<=", date),
		},
		fieldname="exchange_rate",
		order_by="date desc",
	)

	if reverse_rate and flt(reverse_rate) > 0:
		return 1.0 / flt(reverse_rate)

	return None


def validate_multi_currency(doc, company_currency):
	"""
	Validate multi-currency setup on a transaction document.
	Ensures exchange rate exists for non-base-currency orders.
	"""
	if not doc.currency or doc.currency == company_currency:
		return True

	rate = get_exchange_rate(doc.currency, company_currency)
	if not rate:
		frappe.msgprint(
			_("No exchange rate found for {0} → {1}. "
			  "Please add a Currency Exchange entry.").format(
				doc.currency, company_currency
			),
			alert=True,
			indicator="orange",
		)
		return False

	return True

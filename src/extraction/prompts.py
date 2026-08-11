"""Extraction prompt and JSON schema for vision-LLM utility invoice parsing.

This module defines the instructions and structured output schema passed to
the vision model. It contains no API calls — import these constants from
``llm_client.py`` when sending invoice images for extraction.
"""

from __future__ import annotations

from typing import Any

EXTRACTION_PROMPT = """\
You are a utility invoice data extraction assistant. Analyze the provided \
invoice image and extract structured data from it.

Instructions:
1. Detect the language of the invoice document.
2. Extract the fields listed below. Translate all extracted VALUES into \
English (field names stay as given).
3. For dates, use YYYY-MM-DD format. If a date cannot be determined with \
reasonable confidence, use null — do not guess.
4. For utility_type, choose exactly one of: "electricity", "gas", "water", \
"heating", "out_of_scope".
5. If the invoice covers multiple usage categories (e.g. heating AND hot \
water), identify the single highest-cost category and use it as the primary \
usage_quantity and usage_unit. Mention any secondary categories in notes.
6. Set is_out_of_scope to true if the document is not a utility invoice at \
all (e.g. a receipt, bank statement, or unrelated document). In that case, \
set utility_type to "out_of_scope" and use null for fields that do not apply.
7. Provide confidence_score as your self-assessed confidence in the overall \
extraction, from 0.0 (no confidence) to 1.0 (fully confident).
8. Use notes for any caveats, ambiguities, or assumptions you made. Use an \
empty string if there are none.
9. If a field cannot be determined, use null rather than guessing.
10. For usage_quantity specifically: only extract it if the invoice states \
it as a single explicit number (e.g. "142 kWh this period"). Do NOT \
calculate, estimate, average, or derive usage_quantity from a chart, graph, \
trend description, or an "average daily/monthly consumption" figure. If no \
single explicit usage number is stated, set usage_quantity to null and \
usage_unit to null, and explain in notes that usage was not explicitly \
stated.
11. This same no-calculation rule applies to EVERY field, especially \
billing_period_start and billing_period_end. Only use a date that is \
printed on the document itself. Do NOT calculate a period by adding a \
duration (e.g. "one quarter", "one month") to a meter reading date, issue \
date, or any other date. A label like "4th quarter" or "Q4" is NOT \
sufficient on its own to derive start/end dates -- if explicit start and \
end dates are not printed, leave both fields null and explain the \
discrepancy in notes.

Fields to extract:
- vendor_name (string): utility company or supplier name, in English
- invoice_date (string or null): invoice issue date, YYYY-MM-DD
- service_address (string or null): service or billing address, in English
- utility_type (string): one of "electricity", "gas", "water", "heating", \
"out_of_scope"
- usage_quantity (number or null): the physical quantity of the utility \
consumed during the billing period (e.g. kWh of electricity, m³ of water, \
SCM of gas). This is a CONSUMPTION quantity, not a monetary value. Do not \
confuse this with any amount owed or paid.
- usage_unit (string or null): unit for usage_quantity (e.g. "kWh", "m³")
- billing_period_start (string or null): billing period start, YYYY-MM-DD
- billing_period_end (string or null): billing period end, YYYY-MM-DD
- payable_amount (number or null): the total monetary amount due for this \
billing cycle (e.g. "Total a pagar", "Amount Payable", "Total Payable", \
"Gesamtbetrag"). Use the bottom-line total the customer owes now, not a \
subtotal, fixed fee, or "informational" figure.
- currency (string or null): the currency of payable_amount, as a standard \
3-letter code (e.g. "EUR", "INR", "USD"). Infer this from the currency \
symbol or country context if not explicitly labeled.
- detected_language (string): language detected on the invoice
- confidence_score (number): float from 0.0 to 1.0
- is_out_of_scope (boolean): true if this is not a utility invoice
- notes (string): caveats or assumptions; empty string if none

Respond with ONLY valid JSON matching the required schema. Do not wrap the \
JSON in markdown code fences. Do not include any extra commentary.\
"""

RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "vendor_name": {
            "type": "string",
            "description": "Utility vendor or supplier name, translated to English.",
        },
        "invoice_date": {
            "type": "string",
            "nullable": True,
            "description": "Invoice date in YYYY-MM-DD format, or null if unclear.",
        },
        "service_address": {
            "type": "string",
            "nullable": True,
            "description": "Service or billing address, translated to English, or null.",
        },
        "utility_type": {
            "type": "string",
            "enum": ["electricity", "gas", "water", "heating", "out_of_scope"],
            "description": "Primary utility category covered by the invoice.",
        },
        "usage_quantity": {
            "type": "number",
            "nullable": True,
            "description": "Primary usage quantity for the highest-cost category. Consumption, not money.",
        },
        "usage_unit": {
            "type": "string",
            "nullable": True,
            "description": "Unit for usage_quantity (e.g. kWh, m³), or null.",
        },
        "billing_period_start": {
            "type": "string",
            "nullable": True,
            "description": "Billing period start date in YYYY-MM-DD format, or null.",
        },
        "billing_period_end": {
            "type": "string",
            "nullable": True,
            "description": "Billing period end date in YYYY-MM-DD format, or null.",
        },
        "payable_amount": {
            "type": "number",
            "nullable": True,
            "description": "Total monetary amount due for this billing cycle.",
        },
        "currency": {
            "type": "string",
            "nullable": True,
            "description": "3-letter currency code for payable_amount (e.g. EUR, INR).",
        },
        "detected_language": {
            "type": "string",
            "description": "Language detected on the invoice document.",
        },
        "confidence_score": {
            "type": "number",
            "description": "Self-assessed extraction confidence from 0.0 to 1.0.",
        },
        "is_out_of_scope": {
            "type": "boolean",
            "description": "True if the document is not a utility invoice.",
        },
        "notes": {
            "type": "string",
            "description": "Caveats, ambiguities, or assumptions; empty string if none.",
        },
    },
    "required": [
        "vendor_name",
        "invoice_date",
        "service_address",
        "utility_type",
        "usage_quantity",
        "usage_unit",
        "billing_period_start",
        "billing_period_end",
        "payable_amount",
        "currency",
        "detected_language",
        "confidence_score",
        "is_out_of_scope",
        "notes",
    ],
}
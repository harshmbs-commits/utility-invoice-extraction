"""Rule-based (non-LLM) validation checks for extracted invoice data.

These checks catch internally inconsistent or suspicious extractions
(e.g. a billing period that ends before it starts) without needing another
LLM call. Deterministic logic is used here on purpose: it's faster, free,
and fully testable -- see tests/test_validation.py.
"""

from __future__ import annotations

from datetime import date

# Below this confidence, a row is flagged for manual review rather than
# trusted outright.
CONFIDENCE_REVIEW_THRESHOLD = 0.5


def validate_extraction(data: dict) -> dict:
    """Run all rule-based checks on one extracted invoice record.

    Does not raise on failed checks -- it annotates the record instead, so
    the pipeline can decide what to do with flagged rows (e.g. still write
    them to CSV, but mark them for manual review).

    Args:
        data: The dict returned by extract_invoice_data().

    Returns:
        The same dict, with two extra keys added:
          - "validation_flags": list[str] of human-readable issues found
          - "needs_review": bool, True if any flag was raised
    """
    flags: list[str] = []

    if data.get("is_out_of_scope"):
        flags.append("Document flagged as out of scope (not a utility invoice).")

    _check_date_order(data, flags)
    _check_non_negative_usage(data, flags)
    _check_low_confidence(data, flags)
    _check_required_fields_present(data, flags)

    data["validation_flags"] = flags
    data["needs_review"] = len(flags) > 0
    return data


def _check_date_order(data: dict, flags: list[str]) -> None:
    """Flag if billing_period_start is after billing_period_end."""
    start = data.get("billing_period_start")
    end = data.get("billing_period_end")

    if not start or not end:
        return

    try:
        start_date = date.fromisoformat(start)
        end_date = date.fromisoformat(end)
    except (TypeError, ValueError):
        flags.append(
            f"Billing period dates are not valid YYYY-MM-DD values: "
            f"start={start!r}, end={end!r}."
        )
        return

    if start_date > end_date:
        flags.append(
            f"billing_period_start ({start}) is after billing_period_end ({end})."
        )


def _check_non_negative_usage(data: dict, flags: list[str]) -> None:
    """Flag if usage_quantity is negative."""
    usage = data.get("usage_quantity")
    if usage is not None and usage < 0:
        flags.append(f"usage_quantity is negative: {usage}.")


def _check_low_confidence(data: dict, flags: list[str]) -> None:
    """Flag if the model's self-reported confidence is below the threshold."""
    confidence = data.get("confidence_score")
    if confidence is not None and confidence < CONFIDENCE_REVIEW_THRESHOLD:
        flags.append(
            f"Low confidence score ({confidence}) -- below review threshold "
            f"of {CONFIDENCE_REVIEW_THRESHOLD}."
        )


def _check_required_fields_present(data: dict, flags: list[str]) -> None:
    """Flag if core identifying fields are missing on an in-scope invoice."""
    if data.get("is_out_of_scope"):
        return

    if not data.get("vendor_name"):
        flags.append("vendor_name is missing.")
    if not data.get("utility_type"):
        flags.append("utility_type is missing.")
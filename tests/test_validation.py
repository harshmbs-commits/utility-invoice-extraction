"""Automated tests for src/validation/rules.py.

These test the deterministic, rule-based validation logic only -- no LLM
calls happen here, so these tests run instantly and for free. This is by
design: LLM extraction accuracy is checked manually (see README's Testing
Approach section), while this code -- which behaves the same way every
time -- gets proper automated tests.

Run with: pytest tests/test_validation.py -v
"""

from src.validation.rules import validate_extraction


def _base_record(**overrides: object) -> dict:
    """Build a minimal valid record, with any fields overridden for a test."""
    record = {
        "vendor_name": "Test Utility Co",
        "utility_type": "electricity",
        "usage_quantity": 100.0,
        "usage_unit": "kWh",
        "billing_period_start": "2024-01-01",
        "billing_period_end": "2024-01-31",
        "confidence_score": 0.9,
        "is_out_of_scope": False,
    }
    record.update(overrides)
    return record


def test_clean_record_passes_with_no_flags() -> None:
    """A fully valid record should raise no flags and not need review."""
    result = validate_extraction(_base_record())

    assert result["needs_review"] is False
    assert result["validation_flags"] == []


def test_flags_billing_period_start_after_end() -> None:
    """billing_period_start after billing_period_end should be flagged."""
    record = _base_record(
        billing_period_start="2024-05-01",
        billing_period_end="2024-01-01",
    )
    result = validate_extraction(record)

    assert result["needs_review"] is True
    assert any("after" in flag for flag in result["validation_flags"])


def test_missing_billing_dates_are_not_flagged() -> None:
    """Null billing dates are valid (e.g. ambiguous source document) and
    should not trigger the date-order check."""
    record = _base_record(billing_period_start=None, billing_period_end=None)
    result = validate_extraction(record)

    assert result["needs_review"] is False


def test_flags_negative_usage_quantity() -> None:
    """A negative usage_quantity should be flagged."""
    record = _base_record(usage_quantity=-10)
    result = validate_extraction(record)

    assert result["needs_review"] is True
    assert any("negative" in flag for flag in result["validation_flags"])


def test_null_usage_quantity_is_not_flagged() -> None:
    """A null usage_quantity (legitimately unavailable) should not be flagged
    by the negative-usage check."""
    record = _base_record(usage_quantity=None)
    result = validate_extraction(record)

    assert result["needs_review"] is False


def test_flags_low_confidence_score() -> None:
    """A confidence_score below the review threshold should be flagged."""
    record = _base_record(confidence_score=0.2)
    result = validate_extraction(record)

    assert result["needs_review"] is True
    assert any("confidence" in flag.lower() for flag in result["validation_flags"])


def test_high_confidence_score_is_not_flagged() -> None:
    """A confidence_score at or above the threshold should not be flagged."""
    record = _base_record(confidence_score=0.95)
    result = validate_extraction(record)

    assert result["needs_review"] is False


def test_out_of_scope_document_is_flagged() -> None:
    """is_out_of_scope=True should always raise a flag."""
    record = _base_record(is_out_of_scope=True)
    result = validate_extraction(record)

    assert result["needs_review"] is True
    assert any("out of scope" in flag.lower() for flag in result["validation_flags"])


def test_missing_vendor_name_is_flagged_when_in_scope() -> None:
    """An in-scope invoice missing vendor_name should be flagged."""
    record = _base_record(vendor_name="")
    result = validate_extraction(record)

    assert result["needs_review"] is True
    assert any("vendor_name" in flag for flag in result["validation_flags"])


def test_missing_vendor_name_is_not_flagged_when_out_of_scope() -> None:
    """An out-of-scope document isn't expected to have a vendor_name, so it
    shouldn't get a redundant missing-field flag on top of the
    out-of-scope flag."""
    record = _base_record(vendor_name="", is_out_of_scope=True)
    result = validate_extraction(record)

    flags_text = " ".join(result["validation_flags"])
    assert "out of scope" in flags_text.lower()
    assert "vendor_name" not in flags_text


def test_invalid_date_format_is_flagged() -> None:
    """Non-ISO date strings should be flagged rather than crash the check."""
    record = _base_record(
        billing_period_start="17/07/2014",
        billing_period_end="17/09/2014",
    )
    result = validate_extraction(record)

    assert result["needs_review"] is True
    assert any("valid" in flag.lower() for flag in result["validation_flags"])
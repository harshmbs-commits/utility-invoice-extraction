"""Write a list of validated invoice records out to a CSV file.

Takes the structured, validated dictionaries produced by the extraction and
validation modules and writes them to a single clean CSV, one row per
invoice, in the field order required by the assignment.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

# Column order matches the assignment's required fields first, followed by
# the extra fields our pipeline adds (payable amount/currency, language,
# confidence, validation).
CSV_COLUMNS = [
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
    "needs_review",
    "validation_flags",
    "notes",
    "source_file",
]


def write_invoices_to_csv(records: list[dict], output_path: str) -> None:
    """Write validated invoice records to a CSV file.

    Missing columns in any record are filled with empty values rather than
    raising an error, so one malformed record doesn't break the whole run.
    The validation_flags list (if present) is joined into a single
    semicolon-separated string, since CSV cells can't hold Python lists.

    The file is written with a UTF-8 BOM (utf-8-sig) so that special
    characters (e.g. "m³") display correctly when opened directly in
    Excel, which otherwise assumes a different default encoding.

    Args:
        records: List of dicts, one per invoice, as produced by
            extract_invoice_data() and validate_extraction().
        output_path: Where to write the CSV file, e.g.
            "data/output/invoices.csv". Parent directories are created if
            they don't exist.
    """
    rows = [_prepare_row(record) for record in records]

    df = pd.DataFrame(rows, columns=CSV_COLUMNS)

    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False, encoding="utf-8-sig")


def _prepare_row(record: dict) -> dict:
    """Convert one record into a CSV-safe row matching CSV_COLUMNS."""
    row = {column: record.get(column, "") for column in CSV_COLUMNS}

    flags = record.get("validation_flags")
    if isinstance(flags, list):
        row["validation_flags"] = "; ".join(flags)

    return row
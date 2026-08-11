"""Orchestrate the full invoice extraction pipeline.

For each supported file in an input directory:
  1. Convert it to one or more images (src.ingestion.converter)
  2. Extract structured data via LLM, with fallback (src.extraction.llm_client)
  3. Run rule-based validation checks (src.validation.rules)
  4. Collect the result, tagged with its source filename

After processing every file, all results are written to a single CSV
(src.output.csv_writer). One failing invoice does not stop the others --
its error is recorded and processing continues.
"""

from __future__ import annotations

from pathlib import Path

from src.ingestion.converter import convert_to_images
from src.extraction.llm_client import extract_invoice_data
from src.output.csv_writer import write_invoices_to_csv
from src.validation.rules import validate_extraction

SUPPORTED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".webp"}


def run_pipeline(input_dir: str, output_csv_path: str) -> list[dict]:
    """Process every supported invoice file in input_dir and write a CSV.

    Args:
        input_dir: Folder containing invoice files (PDF/JPG/PNG/WEBP).
        output_csv_path: Where to write the resulting CSV.

    Returns:
        The list of processed records (including any error records), in
        case the caller wants to inspect results beyond the CSV.
    """
    input_path = Path(input_dir)
    invoice_files = sorted(
        f for f in input_path.iterdir()
        if f.suffix.lower() in SUPPORTED_EXTENSIONS
    )

    if not invoice_files:
        print(f"No supported invoice files found in {input_dir}.")
        return []

    records: list[dict] = []

    for file_path in invoice_files:
        print(f"Processing {file_path.name} ...")
        record = _process_single_file(file_path)
        records.append(record)

    write_invoices_to_csv(records, output_csv_path)
    print(f"\nWrote {len(records)} record(s) to {output_csv_path}")

    review_count = sum(1 for r in records if r.get("needs_review"))
    if review_count:
        print(f"{review_count} record(s) flagged for manual review.")

    return records


def _process_single_file(file_path: Path) -> dict:
    """Run one file through convert -> extract -> validate.

    If any step fails, returns a minimal error record instead of raising,
    so one bad file doesn't stop the rest of the batch.
    """
    try:
        images = convert_to_images(str(file_path))
        # Per our design decision: one row per invoice. If a PDF has
        # multiple pages, we extract from the first page only.
        extracted = extract_invoice_data(images[0])
        validated = validate_extraction(extracted)
        validated["source_file"] = file_path.name
        return validated
    except Exception as exc:
        print(f"  Failed to process {file_path.name}: {exc}")
        return {
            "source_file": file_path.name,
            "is_out_of_scope": False,
            "needs_review": True,
            "validation_flags": [f"Processing failed: {exc}"],
        }
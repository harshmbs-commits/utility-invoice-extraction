"""Streamlit UI for the utility invoice extraction pipeline.

Lets a user upload multiple invoice files at once, runs each through the
existing pipeline (convert -> extract -> validate), shows a results table
with per-invoice feedback, and offers the combined output as a
downloadable CSV.

Run with: streamlit run app.py
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

# Bridge Streamlit Cloud's secrets manager to environment variables, so the
# same os.environ-based code works both locally (via .env) and when
# deployed (via Streamlit Cloud's Secrets). Safe no-op if no secrets are
# configured (e.g. running purely locally with a .env file instead).
for _key in ("GEMINI_API_KEY", "GROQ_API_KEY"):
    if _key in st.secrets:
        os.environ[_key] = st.secrets[_key]

from src.ingestion.converter import convert_to_images
from src.extraction.llm_client import extract_invoice_data
from src.output.csv_writer import CSV_COLUMNS
from src.validation.rules import validate_extraction

FEEDBACK_LOG_PATH = Path("data/output/feedback_log.csv")


def _log_feedback(record: dict, rating: str) -> None:
    """Append one feedback row to data/output/feedback_log.csv."""
    FEEDBACK_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = pd.DataFrame([{
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source_file": record.get("source_file", ""),
        "vendor_name": record.get("vendor_name", ""),
        "confidence_score": record.get("confidence_score", ""),
        "rating": rating,
    }])
    write_header = not FEEDBACK_LOG_PATH.exists()
    entry.to_csv(FEEDBACK_LOG_PATH, mode="a", header=write_header, index=False)

st.set_page_config(page_title="Utility Invoice Extractor", page_icon="🧾", layout="wide")

st.title("🧾 Utility Invoice Extraction")
st.write(
    "Upload one or more utility invoices (PDF, JPG, PNG, WEBP). "
    "Each file is read by an LLM and converted into structured data."
)

if "records" not in st.session_state:
    st.session_state.records = []

uploaded_files = st.file_uploader(
    "Upload invoices",
    type=["pdf", "jpg", "jpeg", "png", "webp"],
    accept_multiple_files=True,
)

if uploaded_files and st.button("Process invoices", type="primary"):
    records: list[dict] = []
    progress = st.progress(0.0, text="Starting...")

    for i, uploaded_file in enumerate(uploaded_files):
        progress.progress(
            i / len(uploaded_files),
            text=f"Processing {uploaded_file.name} ({i + 1}/{len(uploaded_files)})...",
        )

        suffix = Path(uploaded_file.name).suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(uploaded_file.getvalue())
            tmp_path = tmp.name

        try:
            images = convert_to_images(tmp_path)
            extracted = extract_invoice_data(images[0])
            validated = validate_extraction(extracted)
            validated["source_file"] = uploaded_file.name
            records.append(validated)
        except Exception as exc:
            st.warning(f"Failed to process {uploaded_file.name}: {exc}")
            records.append(
                {
                    "source_file": uploaded_file.name,
                    "is_out_of_scope": False,
                    "needs_review": True,
                    "validation_flags": [f"Processing failed: {exc}"],
                }
            )
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    progress.progress(1.0, text="Done!")
    st.session_state.records = records

records = st.session_state.records

if records:
    in_scope = [r for r in records if not r.get("is_out_of_scope")]
    out_of_scope = [r for r in records if r.get("is_out_of_scope")]

    st.success(f"Processed {len(records)} invoice(s) -- {len(in_scope)} accepted, {len(out_of_scope)} out of scope.")

    # Clear, human callout for anything the model rejected as non-utility.
    for record in out_of_scope:
        st.warning(
            f"**{record.get('source_file', 'This file')}** was not processed as a utility invoice. "
            f"{record.get('notes') or 'It does not appear to be an electricity, gas, water, or heating bill.'} "
            "It has been excluded from the CSV below."
        )

    review_flagged = [r for r in in_scope if r.get("needs_review")]
    if review_flagged:
        st.info(f"{len(review_flagged)} accepted invoice(s) flagged for manual review -- see notes/validation_flags below.")

    # Build display + download rows (accepted invoices only).
    rows = []
    for record in in_scope:
        row = {col: record.get(col, "") for col in CSV_COLUMNS}
        flags = record.get("validation_flags")
        if isinstance(flags, list):
            row["validation_flags"] = "; ".join(flags)
        rows.append(row)

    if rows:
        df = pd.DataFrame(rows, columns=CSV_COLUMNS)
        st.dataframe(df, use_container_width=True)

        csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "⬇️ Download CSV",
            data=csv_bytes,
            file_name="invoices.csv",
            mime="text/csv",
            type="primary",
        )

    st.divider()
    st.subheader("Feedback")
    st.caption("Rate each extraction. Feedback is logged and can be used to spot patterns worth improving.")

    for i, record in enumerate(in_scope):
        confidence = record.get("confidence_score")
        badge = "🟢" if (confidence or 0) >= 0.8 else "🟡" if (confidence or 0) >= 0.5 else "🔴"

        col1, col2, col3 = st.columns([4, 1, 1])
        with col1:
            st.write(f"{badge} **{record.get('source_file')}** -- {record.get('vendor_name', 'Unknown vendor')} (confidence: {confidence})")
        with col2:
            if st.button("👍", key=f"up_{i}"):
                _log_feedback(record, "up")
                st.toast("Thanks for the feedback!")
        with col3:
            if st.button("👎", key=f"down_{i}"):
                _log_feedback(record, "down")
                st.toast("Thanks -- noted for review.")
elif not uploaded_files:
    st.info("Upload one or more invoice files above to get started.")
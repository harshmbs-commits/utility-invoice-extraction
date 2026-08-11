# Utility Invoice Extraction Pipeline

**Live demo:** https://utilityinvoiceextraction.streamlit.app

Extracts structured data (vendor, dates, usage, payable amount) from real-world
multilingual utility invoices (electricity, gas, water, heating) using a
vision-capable LLM, and outputs a clean CSV.

## Sample Data

Four real utility invoices, sourced from four different countries/languages:

| File | Utility | Language | Notes |
|---|---|---|---|
| `Electricity Bill spanish.jpg` | Electricity | Spanish | Iberdrola (Spain); usage shown only as a chart, no explicit total |
| `Gas Invoice.pdf` | Gas | Hindi + English | Indraprastha Gas (India); estimated bill, no explicit usage total |
| `factura_am_bo.png` | Water | Catalan | Aigües Manresa (Spain); quarterly billing, self-contradictory dates on the source document |
| `nebenkosten-...webp` | Heating + Hot Water | German | BRUNATA (Germany); two usage categories in one invoice |

## Architecture
data/sample_invoices/ (PDF/JPG/PNG/WEBP)
|
src/ingestion/converter.py -- standardizes any input into PIL images
|
src/extraction/llm_client.py -- Gemini 3 Flash Preview (primary)
-> Groq Qwen 3.6 27B (fallback)
|
src/validation/rules.py -- rule-based sanity checks (no LLM)
|
src/output/csv_writer.py -- writes data/output/invoices.csv

**Orchestration:** `src/pipeline.py`, run via `main.py`. One failing invoice
does not stop the batch -- it's recorded as an error row instead.

## Field Definitions

The assignment's CSV spec is intentionally ambiguous on a couple of fields.
Here's exactly what this pipeline means by each:

- **usage_quantity**: the physical *consumption* quantity for the billing
  period (e.g. kWh, m³, SCM). This is NOT a monetary value. Only populated
  if the invoice states it as a single explicit number -- never calculated,
  averaged, or estimated from a chart or trend description.
- **payable_amount**: the total monetary amount the customer owes for this
  billing cycle (e.g. "Total a pagar", "Amount Payable"), in the invoice's
  original currency (see `currency` column). This is the bottom-line
  "due now" figure, not a subtotal or an "informational" total.
- **billing_period_start / billing_period_end**: only populated if both
  dates are explicitly printed on the document. Never calculated by adding
  a duration (e.g. "one quarter") to another date on the invoice.
- **needs_review**: True if any rule-based validation check failed (see
  Testing Approach below) -- does not mean the extraction is wrong, just
  that it's worth a human glance.

## Setup

1. `python3 -m venv venv && source venv/bin/activate`
2. `pip install -r requirements.txt`
3. `cp .env.example .env` and fill in your free Gemini + Groq API keys
   (see below for where to get them)
4. `python main.py`
5. Output lands in `data/output/invoices.csv`

**Free API keys:**
- Gemini: https://aistudio.google.com/apikey
- Groq: https://console.groq.com/keys

## Models Used

| Role | Model | Why |
|---|---|---|
| Primary | `gemini-3-flash-preview` (Google GenAI SDK) | Free tier, vision-capable, strong structured-output support |
| Fallback | `qwen/qwen3.6-27b` (Groq) | Free tier, vision-capable; used only if Gemini errors (rate limit, quota, etc.) |

Both were selected on capability, not just cost, since structured-output
reliability mattered most for this task. Model availability on both
platforms changed multiple times during development (see CASE_STUDY.md) --
a real 2026 AI engineering constraint, not a hypothetical one.

## Testing Approach

### Automated tests
`tests/test_validation.py` (11 tests, `pytest`) covers the deterministic
rule-based validation logic: date ordering, non-negative usage, low-confidence
flagging, out-of-scope routing, missing required fields. LLM extraction
itself is not unit-tested -- it's non-deterministic and costs API calls, so
industry practice is to validate its *output* instead, which is what the
manual comparison below does.

Run with: `pytest tests/test_validation.py -v`

### Manual accuracy check
Every field in the generated CSV was manually compared against its source
invoice. Final result: **24/24 independently-checkable fields correct**
across all 4 invoices, after two rounds of bug-fixing (see CASE_STUDY.md
for what was found and fixed).

### Edge cases considered
- Missing/non-standard usage unit (German "STR", not a globally standard unit)
- Usage shown only as a trend/chart, not a clean number (Spanish bill)
- Mixed-language single document (Hindi/English gas bill)
- Multi-category single invoice, requiring a "pick highest-cost category" rule (German heating + hot water)
- Self-contradictory dates on the source document itself (Catalan water bill's quarter label vs. its reading dates)
- A model correctly identifying a document's own internal inconsistency and flagging it in `notes` rather than silently picking one value

### Known limitation
On the German invoice, `utility_type` is labeled "heating" even though the
model's own `notes` field identifies hot water as the actual highest-cost
category. This is a minor mislabeling that wasn't fully fixed given time
constraints -- documented here rather than hidden.

### How I'd improve testing with more time
- A native speaker (or professional translation review) validating extraction
  accuracy in each source language, rather than relying on this project's
  builder + AI assistance for translation-dependent checks
- A larger, more diverse sample set (20+ invoices) to catch rarer edge cases
- Automated regression tests comparing LLM output against a fixed "golden"
  extraction per sample invoice, to catch prompt-change regressions
- Optional LLM-based self-critique as a second validation pass, on top of
  the current rule-based checks

## Normalization Strategy

Beyond extraction, the pipeline actively normalizes several fields so the
output CSV is consistent regardless of the source invoice's original
format or language:

- **Language:** all extracted field values (vendor name, address, notes)
  are translated into English, regardless of the invoice's original
  language (Spanish, Catalan, German, Hindi/English all tested).
  `detected_language` preserves what language the source document was in.
- **Dates:** every date is normalized to ISO 8601 (YYYY-MM-DD), regardless
  of the source format (e.g. "17/07/2014", "02.06.2026", "30/03/2020" all
  become consistent YYYY-MM-DD values).
- **Currency:** monetary amounts are paired with a standardized 3-letter
  currency code (EUR, INR, etc.) rather than a currency symbol, so
  `payable_amount` values are directly comparable/sortable across
  currencies without further parsing.
- **Vendor names:** rendered consistently in English/Latin script even
  when the source uses a different script or language.

## Out-of-Scope Detection: Tested Evidence

Both required layers were tested against a real non-utility document (a
telecom/broadband bill), not just a hypothetical:
is_out_of_scope: True
needs_review: True
validation_flags: ['Document flagged as out of scope (not a utility invoice).']
notes: The document is a telecommunications bill for WiFi and TV services,
which falls outside the scope of traditional utilities (electricity, gas,
water, heating). Usage quantity is not explicitly stated as a single
consumption figure.

This confirms both the prompt-level instruction (model correctly
classifies and explains why a document is out of scope) and the
validation-layer safety net (flags it for review rather than silently
including it) work correctly in practice.

## Assumptions
See CASE_STUDY.md for the full list of assumptions and trade-off decisions
made during this build.
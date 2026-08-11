"""Entry point: run the invoice extraction pipeline end to end.

Processes every invoice in data/sample_invoices/ and writes the results to
data/output/invoices.csv.
"""

from src.pipeline import run_pipeline

if __name__ == "__main__":
    run_pipeline(
        input_dir="data/sample_invoices",
        output_csv_path="data/output/invoices.csv",
    )
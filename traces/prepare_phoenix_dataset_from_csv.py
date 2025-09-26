#!/usr/bin/env python3
"""
Convert the first two columns of the PMS CSV into a Phoenix-friendly dataset.

Input CSV expected format (first two columns used):
- Column 1: Questions (natural language queries)
- Column 2: Generated pipelines (expected/ground-truth pipeline text)

Outputs:
- CSV with columns: id, query, reference
- JSONL with the same fields for alternative imports
"""

import argparse
import csv
import json
from pathlib import Path
from typing import Tuple, List, Dict


def load_and_extract_columns(csv_path: str) -> List[Dict[str, str]]:
    """Load the CSV and extract the first two columns as query/reference.

    The CSV may contain extra columns (remarks, dates, etc.). We only keep the
    first two visible columns and rename them to query and reference.
    """
    rows: List[Dict[str, str]] = []
    # Try a few encodings for robustness
    encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]
    last_err = None
    for enc in encodings:
        try:
            with open(csv_path, "r", encoding=enc, errors="strict") as f:
                reader = csv.reader(f)
                all_rows = list(reader)
            break
        except Exception as e:
            last_err = e
            all_rows = []
            continue
    if not all_rows and last_err:
        raise last_err

    if not all_rows:
        return rows

    # Use the first row as header if present; otherwise treat as data
    header = all_rows[0]
    data_rows = all_rows[1:] if header else all_rows

    if len(header) < 2 and data_rows:
        # No header, treat all rows as data
        data_rows = all_rows

    # Extract first two columns
    for r in data_rows:
        if len(r) < 2:
            continue
        query = (r[0] or "").strip()
        reference = (r[1] or "").strip()
        if query and reference:
            rows.append({"query": query, "reference": reference})

    # Add stable IDs
    for i, item in enumerate(rows):
        item["id"] = f"row_{i+1:04d}"

    return rows


def ensure_output_paths(out_csv: str, out_jsonl: str) -> Tuple[Path, Path]:
    out_csv_path = Path(out_csv).absolute()
    out_jsonl_path = Path(out_jsonl).absolute()
    out_csv_path.parent.mkdir(parents=True, exist_ok=True)
    out_jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    return out_csv_path, out_jsonl_path


def save_outputs(items: List[Dict[str, str]], out_csv: Path, out_jsonl: Path) -> None:
    # CSV
    with open(out_csv, "w", encoding="utf-8", newline="") as fcsv:
        writer = csv.DictWriter(fcsv, fieldnames=["id", "query", "reference"])
        writer.writeheader()
        for item in items:
            writer.writerow({"id": item["id"], "query": item["query"], "reference": item["reference"]})

    # JSONL
    with open(out_jsonl, "w", encoding="utf-8") as fjsonl:
        for item in items:
            fjsonl.write(json.dumps(item, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description="Prepare Phoenix dataset from PMS CSV")
    parser.add_argument(
        "--csv",
        required=True,
        help="Path to source CSV (e.g., /workspace/CRM_HRMS_PMS_Questions(PMS).csv)",
    )
    parser.add_argument(
        "--out_csv",
        default="/workspace/traces/datasets/pms_eval_dataset.csv",
        help="Path to write Phoenix-friendly CSV",
    )
    parser.add_argument(
        "--out_jsonl",
        default="/workspace/traces/datasets/pms_eval_dataset.jsonl",
        help="Path to write Phoenix-friendly JSONL",
    )

    args = parser.parse_args()

    items = load_and_extract_columns(args.csv)
    out_csv_path, out_jsonl_path = ensure_output_paths(args.out_csv, args.out_jsonl)
    save_outputs(items, out_csv_path, out_jsonl_path)

    print("✅ Phoenix dataset files created:")
    print(f" - CSV:   {out_csv_path}")
    print(f" - JSONL: {out_jsonl_path}")
    print(f"📋 Rows: {len(items)} | Columns: ['id', 'query', 'reference']")


if __name__ == "__main__":
    main()



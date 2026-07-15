#!/usr/bin/env python3
"""Extract review candidates from an EPLAN UTF-16 CSV and record PDF provenance.

The output is intentionally non-authoritative: the developer reviews classification,
wiring, device grouping, safety relevance, and physical binding.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


FIELDS = {
    "device_tag": "P_FUNC_DEVICETAG_FULLNAME",
    "page": "P_INSTANCE_PAGEFULLNAME",
    "part_number": "P_ARTICLE_ORDERNR",
    "type_number": "P_ARTICLE_TYPENR",
    "manufacturer": "P_ARTICLE_MANUFACTURER",
    "description_1": "P_ARTICLE_DESCR1",
    "description_2": "P_ARTICLE_DESCR2",
    "description_3": "P_ARTICLE_DESCR3",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_eplan_csv(path: Path) -> tuple[list[dict], list[str]]:
    with path.open("r", encoding="utf-16", newline="") as stream:
        reader = csv.reader(stream, delimiter=";")
        groups = next(reader)
        properties = next(reader)
        indexes = {name: properties.index(prop) for name, prop in FIELDS.items() if prop in properties}
        missing = [prop for prop in FIELDS.values() if prop not in properties]
        rows = []
        for source_row, values in enumerate(reader, start=3):
            record = {name: (values[index].strip() if index < len(values) else "") for name, index in indexes.items()}
            if record.get("device_tag") or record.get("part_number"):
                record["source_row"] = source_row
                record["review_status"] = "unreviewed"
                record["proposed_device_class"] = ""
                record["proposed_physical_device_id"] = ""
                rows.append(record)
    return rows, missing


def pdf_provenance(path: Path) -> dict:
    result = {"path": str(path.resolve()), "sha256": sha256(path), "size_bytes": path.stat().st_size}
    try:
        from pypdf import PdfReader
        reader = PdfReader(path)
        metadata = reader.metadata or {}
        result.update({
            "page_count": len(reader.pages),
            "title": str(metadata.get("/Title") or ""),
            "project_name": str(metadata.get("/ProjectName") or ""),
            "metadata": {str(key): str(value) for key, value in metadata.items()},
        })
        filename = path.stem.lower().replace(" ", "")
        title = (result["title"] + result["project_name"]).lower().replace(" ", "")
        if "rev" in filename and "rev" in title and filename.split("rev", 1)[1][:2] not in title:
            result["review_warning"] = "Filename revision and embedded PDF project/title revision may differ."
    except ModuleNotFoundError:
        result["review_warning"] = "pypdf is not installed; PDF metadata and page count were not extracted."
    return result


def render_markdown(payload: dict) -> str:
    csv_info = payload["sources"]["eplan_csv"]
    pdf_info = payload["sources"].get("electrical_pdf")
    lines = [
        "# EPLAN source review",
        "",
        "> Extraction only. Device classification, wiring verification, safety scope and physical binding remain developer decisions.",
        "",
        f"- CSV: `{csv_info['path']}`",
        f"- SHA-256: `{csv_info['sha256']}`",
        f"- Candidate rows: {csv_info['candidate_count']}",
        f"- Unique device tags: {csv_info['unique_device_tags']}",
    ]
    if pdf_info:
        lines.extend(["", f"- PDF: `{pdf_info['path']}`", f"- PDF pages: {pdf_info.get('page_count', 'not read')}"])
        if pdf_info.get("review_warning"):
            lines.append(f"- Review warning: {pdf_info['review_warning']}")
    lines.extend(["", "## Manufacturers", "", "| Code | Rows |", "| --- | ---: |"])
    lines.extend(f"| {name or '(empty)'} | {count} |" for name, count in csv_info["manufacturers"].items())
    lines.extend(["", "## Next review", "", "Use `eplan-review-candidates.json` to confirm tags, merge repeated article rows, classify devices, and then copy only approved records into the controller/device/group surveys.", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract traceable review candidates from EPLAN sources")
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--pdf", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    csv_path = args.csv.resolve()
    rows, missing = read_eplan_csv(csv_path)
    manufacturers = Counter(row.get("manufacturer", "") for row in rows)
    payload = {
        "schema_version": 1,
        "authoritative": False,
        "sources": {
            "eplan_csv": {
                "path": str(csv_path), "sha256": sha256(csv_path), "size_bytes": csv_path.stat().st_size,
                "encoding": "UTF-16", "delimiter": ";", "header_rows": 2,
                "candidate_count": len(rows),
                "unique_device_tags": len({row["device_tag"] for row in rows if row.get("device_tag")}),
                "missing_properties": missing,
                "manufacturers": dict(manufacturers.most_common()),
            }
        },
        "candidates": rows,
    }
    if args.pdf:
        payload["sources"]["electrical_pdf"] = pdf_provenance(args.pdf.resolve())
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "eplan-review-candidates.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (output_dir / "eplan-source-review.md").write_text(render_markdown(payload), encoding="utf-8")
    print(f"Wrote {len(rows)} EPLAN review candidates to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

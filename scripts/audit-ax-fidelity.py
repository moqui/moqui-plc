#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from ax_port.fidelity import compare_comments, compare_leading_indentation
from ax_port.policy import MANUAL_AX_OVERRIDE_STEMS


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit source fidelity between canonical IEC and staged AX files.")
    parser.add_argument("--source-root", default=str(REPO_ROOT / "iec61131" / "moqui"))
    parser.add_argument("--target-root", default=str(REPO_ROOT / "simatic-ax" / "src" / "moqui"))
    parser.add_argument("--report", default=str(REPO_ROOT / "simatic-ax" / "docs" / "fidelity-report.md"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source_root = Path(args.source_root).resolve()
    target_root = Path(args.target_root).resolve()
    report_path = Path(args.report).resolve()

    findings = []
    compared = 0
    overrides = 0
    for target_path in sorted(target_root.rglob("*.st")):
        relative = target_path.relative_to(target_root)
        source_path = source_root / relative
        if not source_path.exists():
            continue
        compared += 1
        if relative.with_suffix("") in MANUAL_AX_OVERRIDE_STEMS:
            overrides += 1
            continue
        source = source_path.read_text(encoding="utf-8", errors="ignore")
        target = target_path.read_text(encoding="utf-8", errors="ignore")
        findings.extend(compare_comments(relative, source, target))
        findings.extend(compare_leading_indentation(relative, source, target))

    lines = [
        "# IEC61131 -> SIMATIC AX fidelity audit",
        "",
        f"Compared generated files: **{compared}**",
        f"Manual AX overrides skipped: **{overrides}**",
        f"Findings: **{len(findings)}**",
        "",
        "The audit intentionally skips manually maintained AX overrides and checks generated files for comment and indentation drift.",
        "",
    ]
    for finding in findings:
        lines.extend([
            f"## `{finding.relative_path.as_posix()}`",
            "",
            f"Category: `{finding.category}`",
            "",
            "```diff",
            finding.detail,
            "```",
            "",
        ])
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"Compared: {compared}; overrides skipped: {overrides}; findings: {len(findings)}")
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()

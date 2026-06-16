from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from pathlib import Path


COMMENT_RE = re.compile(r"\(\*.*?\*\)", re.DOTALL)


@dataclass(frozen=True)
class FidelityFinding:
    relative_path: Path
    category: str
    detail: str


def extract_comments(text: str) -> list[str]:
    return COMMENT_RE.findall(text.replace("\r\n", "\n").replace("\r", "\n"))


def compare_comments(relative_path: Path, source: str, target: str) -> list[FidelityFinding]:
    source_comments = extract_comments(source)
    target_comments = extract_comments(target)
    if source_comments == target_comments:
        return []
    diff = "\n".join(
        difflib.unified_diff(
            source_comments,
            target_comments,
            fromfile="IEC comments",
            tofile="AX comments",
            lineterm="",
            n=1,
        )
    )
    return [FidelityFinding(relative_path, "comment_difference", diff[:4000])]


def compare_leading_indentation(relative_path: Path, source: str, target: str) -> list[FidelityFinding]:
    source_lines = source.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    target_lines = target.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    if len(source_lines) != len(target_lines):
        return []
    changed: list[int] = []
    for index, (left, right) in enumerate(zip(source_lines, target_lines), start=1):
        left_indent = left[: len(left) - len(left.lstrip(" \t"))]
        right_indent = right[: len(right) - len(right.lstrip(" \t"))]
        if left_indent != right_indent:
            changed.append(index)
    if not changed:
        return []
    preview = ", ".join(str(line) for line in changed[:50])
    return [FidelityFinding(relative_path, "indentation_difference", f"lines: {preview}")]

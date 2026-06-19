#!/usr/bin/env python3
"""
Mechanical converter for IEC61131 -> SIMATIC AX preview generation.

Goals:
- preserve the IEC61131 directory structure in a preview area under simatic-ax
- apply only low-risk, mechanical text transformations
- generate a report of files that still contain AX-blocking patterns

This script is intentionally conservative: it does not try to "finish" the
port, it only accelerates the repetitive steps and highlights remaining work.
"""

from __future__ import annotations

import argparse
import dataclasses
import re
import shutil
import sys
from pathlib import Path
from typing import Iterable

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

from ax_port.policy import MOTION_MANUAL_OVERRIDE_STEMS  # noqa: E402

TEXT_FILE_SUFFIXES = {".pou", ".dut", ".gvl", ".st", ".conf", ".md", ".csv", ".axrecipe", ".txtrecipe"}

PRESERVE_TARGET_RELATIVE_STEMS = MOTION_MANUAL_OVERRIDE_STEMS


@dataclasses.dataclass
class FileReport:
    path: Path
    changed: bool
    patterns: list[str]
    occurrences: dict[str, list[int]]


MECHANICAL_REPLACEMENTS: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"\bREFERENCE\s+TO\b"), "REF_TO", "REFERENCE TO -> REF_TO"),
    (re.compile(r"\bMC_DIRECTION\b"), "MC_Direction", "Normalize MC direction enum spelling"),
]
REF_ASSIGN_RE = re.compile(
    r"(?P<indent>^[ \t]*)(?P<lhs>[A-Za-z_][A-Za-z0-9_\.\[\]]*)\s+REF=\s+(?P<rhs>[^;\r\n]+);",
    re.MULTILINE,
)
CONTROL_END_RE = re.compile(r"\b(END_IF|END_CASE|END_FOR|END_WHILE|END_REPEAT)\b(?!\s*;)")
ACTUATOR_REF_DECL_RE = re.compile(r"(?m)^(\s*)ref(\s*:\s*REAL\s*;)")
ACTUATOR_REF_ARG_RE = re.compile(r"(?m)^(\s*)ref(\s*:=)")
MOQUISTART_REMOVABLE_DECL_RE = re.compile(
    r"(?m)^[ \t]*(?:runNetworkDgs\s*:\s*NetworkDiagnostics;|inputProcessing\s*:\s*InputSignalUpdate;|outputProcessing\s*:\s*OutputSignalUpdate;)[ \t]*\n?"
)
WORKEFFORT_DECL_RE = re.compile(r"(?m)^[ \t]*workEffort\s*:\s*WorkEffort;[ \t]*\n?")
EC_NAMESPACE_RE = re.compile(r"\bec\.")
OPERATINGMODE_TYPO_RE = re.compile(r"\boperatingMode(?=[#\.])")
SIGNAL_OUTPUT_ACTION_REPLACEMENTS = {
    "SignalOutputAction#None": "DWORD#16#0000",
    "SignalOutputAction#EmergencyStop": "DWORD#16#0001",
    "SignalOutputAction#ImmediateStop": "DWORD#16#0002",
    "SignalOutputAction#OnPhaseStop": "DWORD#16#0003",
    "SignalOutputAction#Inhibition": "DWORD#16#0004",
    "SignalOutputAction.None": "DWORD#16#0000",
    "SignalOutputAction.EmergencyStop": "DWORD#16#0001",
    "SignalOutputAction.ImmediateStop": "DWORD#16#0002",
    "SignalOutputAction.OnPhaseStop": "DWORD#16#0003",
    "SignalOutputAction.Inhibition": "DWORD#16#0004",
}

ENUM_TYPE_BLOCK_RE = re.compile(
    r"TYPE\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*:\s*\((?P<body>.*?)\)\s*;\s*END_TYPE",
    re.DOTALL,
)
TYPED_ENUM_TYPE_BLOCK_RE = re.compile(
    r"TYPE\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*:\s*\((?P<body>.*?)\)\s*[A-Za-z_][A-Za-z0-9_]*\s*;\s*END_TYPE",
    re.DOTALL,
)
ENUM_MEMBER_VALUE_RE = re.compile(r"(?P<member>\b[A-Za-z_][A-Za-z0-9_]*\b)\s*:=\s*(?P<value>[^,\r\n)]+)")
END_STRUCT_END_TYPE_RE = re.compile(r"END_STRUCT\s+END_TYPE")
END_UNION_END_TYPE_RE = re.compile(r"END_UNION\s+END_TYPE")
TYPE_UNION_RE = re.compile(r"\bTYPE\s+([A-Za-z_][A-Za-z0-9_]*)\s*:\s*UNION\b")


PATTERN_CHECKS: list[tuple[str, re.Pattern[str]]] = [
    ("codesys_recipe_management", re.compile(r"\bRecipe_Management\b")),
    ("codesys_motion_namespace", re.compile(r"\bSM3_Basic\b")),
    ("attribute_annotation", re.compile(r"\{attribute\s+'[^']+'\}")),
    ("reference_to", re.compile(r"\bREFERENCE\s+TO\b")),
]


def is_text_file(path: Path) -> bool:
    return path.suffix.lower() in TEXT_FILE_SUFFIXES


def normalize_line_endings(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def convert_attribute_annotations(text: str) -> tuple[str, bool]:
    changed = False
    lines: list[str] = []
    for line in text.split("\n"):
        match = re.fullmatch(r"\{attribute\s+'([^']+)'\}", line.strip())
        if match:
            changed = True
            lines.append(f"(* AX_TODO: removed CODESYS attribute '{match.group(1)}' during automatic conversion. *)")
        else:
            lines.append(line)
    return "\n".join(lines), changed


def remove_explicit_enum_values(text: str) -> tuple[str, bool]:
    changed = False

    def replace_enum_block(match: re.Match[str]) -> str:
        nonlocal changed
        body = match.group("body")
        new_body, replacements = ENUM_MEMBER_VALUE_RE.subn(r"\g<member>", body)
        if replacements:
            changed = True
        return f"TYPE {match.group('name')} : ({new_body}); END_TYPE"

    text = TYPED_ENUM_TYPE_BLOCK_RE.sub(replace_enum_block, text)
    text = ENUM_TYPE_BLOCK_RE.sub(replace_enum_block, text)
    return text, changed


def convert_ref_assignments(text: str) -> tuple[str, bool]:
    changed = False

    def replace_ref_assignment(match: re.Match[str]) -> str:
        nonlocal changed
        changed = True
        indent = match.group("indent")
        lhs = match.group("lhs")
        rhs = match.group("rhs").strip()
        return f"{indent}{lhs} := REF({rhs});"

    return REF_ASSIGN_RE.sub(replace_ref_assignment, text), changed


def normalize_struct_and_union_endings(text: str) -> tuple[str, bool]:
    changed = False
    result, union_type_count = TYPE_UNION_RE.subn(r"TYPE \1 : STRUCT", text)
    if union_type_count:
        changed = True
    result, struct_count = END_STRUCT_END_TYPE_RE.subn("END_STRUCT; END_TYPE", result)
    if struct_count:
        changed = True
    result, union_count = END_UNION_END_TYPE_RE.subn("END_UNION; END_TYPE", result)
    if union_count:
        changed = True
    result, union_end_count = re.subn(r"\bEND_UNION\b", "END_STRUCT", result)
    if union_end_count:
        changed = True
    return result, changed


def normalize_control_endings(text: str) -> tuple[str, bool]:
    result, replacements = CONTROL_END_RE.subn(r"\1;", text)
    return result, replacements > 0


def flatten_nested_comments(text: str) -> tuple[str, bool]:
    changed = False
    result: list[str] = []
    i = 0
    in_comment = False
    nested_depth = 0
    while i < len(text):
        pair = text[i:i + 2]
        if not in_comment:
            if pair == "(*":
                in_comment = True
                result.append(pair)
                i += 2
                continue
            result.append(text[i])
            i += 1
            continue

        if pair == "(*":
            nested_depth += 1
            changed = True
            result.append("[")
            i += 2
            continue

        if pair == "*)":
            if nested_depth > 0:
                nested_depth -= 1
                changed = True
                result.append("]")
                i += 2
                continue
            in_comment = False
            result.append(pair)
            i += 2
            continue

        result.append(text[i])
        i += 1

    return "".join(result), changed


def rename_actuator_ref_identifiers(text: str) -> tuple[str, bool]:
    changed = False
    result, decl_count = ACTUATOR_REF_DECL_RE.subn(r"\1referenceValue\2", text)
    if decl_count:
        changed = True
    result, arg_count = ACTUATOR_REF_ARG_RE.subn(r"\1referenceValue\2", result)
    if arg_count:
        changed = True
    return result, changed


def remove_ax_excluded_declarations(relative: Path, text: str) -> tuple[str, bool]:
    result = text
    count = 0
    if relative.as_posix() == "framework/src/start/MoquiStart.st":
        result, count = MOQUISTART_REMOVABLE_DECL_RE.subn("", result)
        external_line = "\t\tenable, init, error, reset : BOOL;"
        replacement_line = "\t\tenable, init, error, reset, autoReset : BOOL;"
        if external_line in result:
            result = result.replace(external_line, replacement_line)
            count += 1
    if relative.as_posix() == "runtime/component/mantle-hvac/src/main/mantle/hvac/Main.st":
        external_line = "\t\tdev : DeviceFacade;"
        replacement_line = "\t\tclks : Clocks;\n\t\tdev : DeviceFacade;"
        if external_line in result and "clks : Clocks;" not in result:
            result = result.replace(external_line, replacement_line)
            count += 1
    result, workeffort_count = WORKEFFORT_DECL_RE.subn("", result)
    count += workeffort_count
    return result, count > 0


def normalize_ax_globals_and_bitmasks(text: str) -> tuple[str, bool]:
    changed = False
    result, count = EC_NAMESPACE_RE.subn("", text)
    if count:
        changed = True
    result, typo_count = OPERATINGMODE_TYPO_RE.subn("OperatingMode", result)
    if typo_count:
        changed = True
    for source_text, target_text in SIGNAL_OUTPUT_ACTION_REPLACEMENTS.items():
        if source_text in result:
            result = result.replace(source_text, target_text)
            changed = True
    return result, changed


def ensure_unit_closure(relative: Path, text: str) -> tuple[str, bool]:
    stripped = text.rstrip()
    if not stripped:
        return text, False

    unit_matches = list(re.finditer(r"(?m)^\s*(FUNCTION_BLOCK|FUNCTION|PROGRAM)\b", stripped))
    if not unit_matches:
        return text, False

    unit_match = unit_matches[-1]
    unit_kind = unit_match.group(1)
    trailing_text = stripped[unit_match.end():]

    if unit_kind == "FUNCTION_BLOCK" and not re.search(r"(?m)^\s*END_FUNCTION_BLOCK\s*$", trailing_text):
        return stripped + "\nEND_FUNCTION_BLOCK\n", True
    if unit_kind == "FUNCTION" and not re.search(r"(?m)^\s*END_FUNCTION\s*$", trailing_text):
        return stripped + "\nEND_FUNCTION\n", True
    if unit_kind == "PROGRAM" and not re.search(r"(?m)^\s*END_PROGRAM\s*$", trailing_text):
        return stripped + "\nEND_PROGRAM\n", True
    return text, False


def convert_enum_member_access(text: str, enum_type_names: Iterable[str]) -> tuple[str, bool]:
    changed = False
    result = text
    for enum_name in sorted(set(enum_type_names), key=len, reverse=True):
        pattern = re.compile(rf"\b{re.escape(enum_name)}\.([A-Za-z_][A-Za-z0-9_]*)\b")
        result, count = pattern.subn(rf"{enum_name}#\1", result)
        if count:
            changed = True
    return result, changed


def apply_mechanical_replacements(relative: Path, text: str, enum_type_names: Iterable[str]) -> tuple[str, bool]:
    changed = False
    result = text
    result, removed_decls_changed = remove_ax_excluded_declarations(relative, result)
    if removed_decls_changed:
        changed = True
    result, globals_and_bitmasks_changed = normalize_ax_globals_and_bitmasks(result)
    if globals_and_bitmasks_changed:
        changed = True
    result, attr_changed = convert_attribute_annotations(result)
    if attr_changed:
        changed = True
    result, enum_changed = remove_explicit_enum_values(result)
    if enum_changed:
        changed = True
    result, ref_assign_changed = convert_ref_assignments(result)
    if ref_assign_changed:
        changed = True
    result, type_endings_changed = normalize_struct_and_union_endings(result)
    if type_endings_changed:
        changed = True
    result, control_endings_changed = normalize_control_endings(result)
    if control_endings_changed:
        changed = True
    result, nested_comment_changed = flatten_nested_comments(result)
    if nested_comment_changed:
        changed = True
    result, ref_rename_changed = rename_actuator_ref_identifiers(result)
    if ref_rename_changed:
        changed = True
    result, enum_access_changed = convert_enum_member_access(result, enum_type_names)
    if enum_access_changed:
        changed = True
    for pattern, replacement, _description in MECHANICAL_REPLACEMENTS:
        new_result = pattern.sub(replacement, result)
        if new_result != result:
            changed = True
            result = new_result
    result, unit_closure_changed = ensure_unit_closure(relative, result)
    if unit_closure_changed:
        changed = True
    return result, changed


def collect_local_enum_type_names(source_root: Path) -> set[str]:
    enum_type_names: set[str] = set()
    enum_type_re = re.compile(r"TYPE\s+([A-Za-z_][A-Za-z0-9_]*)\s*:\s*\(", re.DOTALL)
    for source_path in sorted(source_root.rglob("*")):
        if not source_path.is_file() or not is_text_file(source_path):
            continue
        text = normalize_line_endings(source_path.read_text(encoding="utf-8", errors="ignore"))
        for match in enum_type_re.finditer(text):
            enum_type_names.add(match.group(1))
    return enum_type_names


def detect_patterns(text: str) -> list[str]:
    found: list[str] = []
    for label, pattern in PATTERN_CHECKS:
        if pattern.search(text):
            found.append(label)
    return found


def collect_occurrences(text: str) -> dict[str, list[int]]:
    occurrences: dict[str, list[int]] = {}
    lines = text.split("\n")
    for label, pattern in PATTERN_CHECKS:
        hits: list[int] = []
        for idx, line in enumerate(lines, start=1):
            if pattern.search(line):
                hits.append(idx)
        if hits:
            occurrences[label] = hits
    return occurrences


def should_preserve_manual_override(relative: Path, target_root: Path) -> bool:
    if relative.with_suffix("") not in PRESERVE_TARGET_RELATIVE_STEMS:
        return False
    target_dir = target_root / relative.parent
    stem = relative.stem
    for candidate in target_dir.glob(stem + ".*"):
        if candidate.is_file():
            return True
    return False


def collect_preserved_manual_overrides(target_root: Path) -> dict[Path, str]:
    preserved: dict[Path, str] = {}
    for relative_stem in PRESERVE_TARGET_RELATIVE_STEMS:
        target_dir = target_root / relative_stem.parent
        if not target_dir.exists():
            continue
        for candidate in sorted(target_dir.glob(relative_stem.name + ".*")):
            if candidate.is_file():
                preserved[relative_stem.with_suffix(".st")] = candidate.read_text(
                    encoding="utf-8",
                    errors="ignore",
                )
                break
    return preserved


def clean_target_root(target_root: Path) -> None:
    if target_root.exists():
        shutil.rmtree(target_root)
    target_root.mkdir(parents=True, exist_ok=True)


def convert_tree(
    source_root: Path,
    target_root: Path,
    preserved_overrides: dict[Path, str],
    enum_type_names: Iterable[str],
) -> list[FileReport]:
    reports: list[FileReport] = []
    for source_path in sorted(source_root.rglob("*")):
        relative = source_path.relative_to(source_root)
        target_path = target_root / relative

        if source_path.is_dir():
            target_path.mkdir(parents=True, exist_ok=True)
            continue

        if relative in preserved_overrides:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            preserved_text = preserved_overrides.get(relative)
            if preserved_text is not None:
                target_path.write_text(preserved_text, encoding="utf-8", newline="\n")
            reports.append(
                FileReport(
                    path=relative,
                    changed=False,
                    patterns=["preserved_manual_ax_override"],
                    occurrences={"preserved_manual_ax_override": []},
                )
            )
            continue

        target_path.parent.mkdir(parents=True, exist_ok=True)

        if not is_text_file(source_path):
            target_path.write_bytes(source_path.read_bytes())
            reports.append(FileReport(path=relative, changed=False, patterns=[], occurrences={}))
            continue

        original = normalize_line_endings(source_path.read_text(encoding="utf-8", errors="ignore"))
        converted, changed = apply_mechanical_replacements(relative, original, enum_type_names)
        patterns = detect_patterns(converted)
        occurrences = collect_occurrences(converted)
        target_path.write_text(converted, encoding="utf-8", newline="\n")
        reports.append(FileReport(path=relative, changed=changed, patterns=patterns, occurrences=occurrences))
    return reports


def write_report(report_path: Path, reports: list[FileReport], source_root: Path, target_root: Path) -> None:
    changed_files = [r for r in reports if r.changed]
    flagged_files = [r for r in reports if r.patterns]
    motion_files = [r for r in reports if "codesys_motion_namespace" in r.patterns or "motion" in r.path.parts]
    recipe_backend_files = [r for r in reports if "codesys_recipe_management" in r.patterns]

    lines: list[str] = []
    lines.append("# IEC61131 -> AX conversion report")
    lines.append("")
    lines.append(f"Source: `{source_root}`")
    lines.append(f"Target: `{target_root}`")
    lines.append("")
    lines.append(f"Converted files: {len(reports)}")
    lines.append(f"Files changed mechanically: {len(changed_files)}")
    lines.append(f"Files still containing flagged patterns: {len(flagged_files)}")
    lines.append("")

    lines.append("## Mechanical replacements")
    lines.append("")
    for _pattern, _replacement, description in MECHANICAL_REPLACEMENTS:
        lines.append(f"- {description}")
    lines.append("- Convert CODESYS `{attribute '...'}` annotations into `AX_TODO` comments")
    lines.append("- Remove explicit numeric assignments from enum members for AX compatibility")
    lines.append("- Convert CODESYS reference assignments `refVar REF= x;` into AX `refVar := REF(x);`")
    lines.append("- Convert `UNION` payload types to `STRUCT` and normalize type endings for AX")
    lines.append("")

    lines.append("## Remaining flagged patterns")
    lines.append("")
    lines.append("- `codesys_recipe_management`: CODESYS recipe backend still present")
    lines.append("- `codesys_motion_namespace`: motion namespace still tied to CODESYS/SM3")
    lines.append("- `attribute_annotation`: attribute syntax may need AX review")
    lines.append("- `reference_to`: manual review needed if any remained")
    lines.append("- `preserved_manual_ax_override`: target file intentionally kept because it already contains AX-specific manual work")
    lines.append("")

    lines.append("## Motion-related files")
    lines.append("")
    for item in motion_files:
        lines.append(f"- `{item.path}`")
    lines.append("")

    lines.append("## Recipe backend files still tied to CODESYS")
    lines.append("")
    for item in recipe_backend_files:
        lines.append(f"- `{item.path}`")
    lines.append("")

    lines.append("## Files with flagged patterns")
    lines.append("")
    for item in flagged_files:
        details: list[str] = []
        for pattern in item.patterns:
            if pattern in item.occurrences and item.occurrences[pattern]:
                details.append(f"{pattern} @ {', '.join(str(v) for v in item.occurrences[pattern])}")
            else:
                details.append(pattern)
        lines.append(f"- `{item.path}`: {'; '.join(details)}")
    lines.append("")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply the first mechanical IEC61131 -> AX text conversions.")
    parser.add_argument(
        "--source-root",
        default=str(REPO_ROOT / "iec61131"),
        help="IEC61131 source tree to convert.",
    )
    parser.add_argument(
        "--target-root",
        default=str(REPO_ROOT / "simatic-ax" / "_conversion-preview"),
        help="Target preview AX tree to overwrite/update.",
    )
    parser.add_argument(
        "--subdir",
        default="moqui",
        help="Subtree inside source/target roots to convert mechanically.",
    )
    parser.add_argument(
        "--report",
        default=str(REPO_ROOT / "simatic-ax" / "docs" / "conversion-report.md"),
        help="Markdown report path.",
    )
    args = parser.parse_args()

    source_base_root = Path(args.source_root)
    target_base_root = Path(args.target_root)
    source_root = source_base_root / args.subdir
    target_root = target_base_root / args.subdir
    report_path = Path(args.report)

    preserved_overrides = collect_preserved_manual_overrides(target_root)
    clean_target_root(target_root)
    enum_type_names = collect_local_enum_type_names(source_root)
    reports = convert_tree(source_root, target_root, preserved_overrides, enum_type_names)
    source_configuration = source_base_root / "configuration.st"
    target_configuration = target_base_root / "configuration.st"
    if source_configuration.exists():
        target_configuration.parent.mkdir(parents=True, exist_ok=True)
        target_configuration.write_text(
            source_configuration.read_text(encoding="utf-8", errors="ignore"),
            encoding="utf-8",
            newline="\n",
        )
    write_report(report_path, reports, source_root, target_root)


if __name__ == "__main__":
    main()

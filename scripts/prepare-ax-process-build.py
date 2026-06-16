#!/usr/bin/env python3
"""
Prepare the official SIMATIC AX source tree from the canonical IEC61131 export.

Goals:
- treat `iec61131/moqui/...` as the canonical ST source tree
- generate the reduced, process-only AX tree directly under `simatic-ax/src/moqui`
- preserve manual AX overrides already introduced during the port
- generate `simatic-ax/src/configuration.st`
"""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

from ax_port.compatibility import apply_file_compatibility
from ax_port.policy import POLICIES
from ax_port.transforms import convert_text as conservative_convert_text


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_SOURCE_ROOT = REPO_ROOT / "iec61131" / "moqui"
DEFAULT_SIMATIC_AX_ROOT = REPO_ROOT / "simatic-ax"
DEFAULT_TARGET_ROOT = DEFAULT_SIMATIC_AX_ROOT / "src" / "moqui"
DEFAULT_LEGACY_PRESERVE_ROOT = DEFAULT_SIMATIC_AX_ROOT / "moqui"
DEFAULT_MANUAL_PRESERVE_ROOT = DEFAULT_SIMATIC_AX_ROOT / "src-manual"

# Profile-specific apax.yml templates (process excludes the Motion library to avoid ABI mismatch).
APAX_TEMPLATE_BY_PROFILE: dict[str, Path] = {
    "process": DEFAULT_SIMATIC_AX_ROOT / "apax-process.yml",
    "motion": DEFAULT_SIMATIC_AX_ROOT / "apax-motion.yml",
    "full": DEFAULT_SIMATIC_AX_ROOT / "apax-motion.yml",
}

SOURCE_FILE_SUFFIXES = {".st"}
ALLOWED_UTIL_STEMS = {
    "clocks",
    "clockgeneration",
    "iirfilter",
    "meanfiltertype",
    "nowtimestamp",
    "sshapedfunc",
}

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare the official SIMATIC AX source tree.")
    parser.add_argument("--source-root", default=str(DEFAULT_SOURCE_ROOT), help="Canonical IEC61131 moqui source root.")
    parser.add_argument(
        "--profile",
        choices=sorted(POLICIES),
        default="process",
        help="Staging policy. process preserves the current compiling baseline; full stages all portable main/runtime code.",
    )
    parser.add_argument("--target-root", default=str(DEFAULT_TARGET_ROOT), help="Official AX source root under src/moqui.")
    parser.add_argument(
        "--legacy-preserve-root",
        default=str(DEFAULT_LEGACY_PRESERVE_ROOT),
        help="Legacy AX tree used only as a fallback source for preserved manual overrides.",
    )
    return parser.parse_args()


def normalize_line_endings(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def collect_local_enum_type_names(source_root: Path) -> set[str]:
    enum_type_names: set[str] = set()
    enum_type_re = re.compile(r"TYPE\s+([A-Za-z_][A-Za-z0-9_]*)\s*:\s*\(", re.DOTALL)
    for source_path in sorted(source_root.rglob("*")):
        if not source_path.is_file() or source_path.suffix.lower() not in SOURCE_FILE_SUFFIXES:
            continue
        text = normalize_line_endings(source_path.read_text(encoding="utf-8", errors="ignore"))
        for match in enum_type_re.finditer(text):
            enum_type_names.add(match.group(1))
    return enum_type_names


def ensure_unit_closure(text: str) -> tuple[str, bool]:
    """Add an AX unit terminator only when the exported IEC object omitted it."""
    stripped = text.rstrip()
    if not stripped:
        return text, False
    unit_matches = list(re.finditer(r"(?m)^\s*(FUNCTION_BLOCK|FUNCTION|PROGRAM)\b", stripped))
    if not unit_matches:
        return text, False
    unit_match = unit_matches[-1]
    unit_kind = unit_match.group(1)
    trailing_text = stripped[unit_match.end():]
    closing = {
        "FUNCTION_BLOCK": "END_FUNCTION_BLOCK",
        "FUNCTION": "END_FUNCTION",
        "PROGRAM": "END_PROGRAM",
    }[unit_kind]
    if re.search(rf"(?m)^\s*{closing}\s*$", trailing_text):
        return text, False
    return stripped + f"\n{closing}\n", True


def convert_text(relative: Path, text: str, enum_type_names: set[str]) -> tuple[str, list[str]]:
    converted = conservative_convert_text(relative, text, enum_type_names)
    result = converted.text
    applied = list(converted.applied)

    # Explicit compatibility rewrites retained from the already compiling AX baseline.
    compatibility = apply_file_compatibility(relative, result)
    result = compatibility.text
    applied.extend(compatibility.applied)
    result, changed = ensure_unit_closure(result)
    if changed:
        applied.append("ensure_unit_closure")
    return result, applied


def should_include(relative_path: Path, profile: str) -> bool:
    policy = POLICIES[profile]
    if not policy.includes(relative_path):
        return False

    # Keep the proven process profile restrictions until each additional file is compiled.
    if profile in {"process", "motion"}:
        relative_posix = relative_path.as_posix().lower()
        stem_lower = relative_path.stem.lower()
        if "framework/src/main/org/moqui/util/" in relative_posix and stem_lower not in ALLOWED_UTIL_STEMS:
            return False
        if (
            "framework/src/main/org/moqui/device/" in relative_posix
            and stem_lower.startswith("process")
            and stem_lower != "processpid"
        ):
            return False
    return True


def collect_preserved_manual_overrides(
    search_roots: list[Path],
    manual_override_stems: frozenset,
) -> dict[Path, str]:
    """Search roots in priority order; first hit wins."""
    preserved: dict[Path, str] = {}
    for relative_stem in manual_override_stems:
        relative_st = relative_stem.with_suffix(".st")
        for root in search_roots:
            candidate = root / relative_st
            if candidate.exists() and candidate.is_file():
                preserved[relative_st] = candidate.read_text(encoding="utf-8", errors="ignore")
                break
    return preserved




def collect_target_assets(target_root: Path) -> dict[Path, bytes]:
    """Preserve non-ST assets (recipes, CSV schemas, etc.) across source staging."""
    assets: dict[Path, bytes] = {}
    if not target_root.exists():
        return assets
    for candidate in target_root.rglob("*"):
        if candidate.is_file() and candidate.suffix.lower() != ".st":
            assets[candidate.relative_to(target_root)] = candidate.read_bytes()
    return assets


def restore_target_assets(target_root: Path, assets: dict[Path, bytes]) -> None:
    for relative, content in assets.items():
        target_path = target_root / relative
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(content)

def clean_target_root(target_root: Path) -> None:
    if target_root.exists():
        shutil.rmtree(target_root)
    target_root.mkdir(parents=True, exist_ok=True)


def extract_global_section(source_path: Path) -> str:
    text = normalize_line_endings(source_path.read_text(encoding="utf-8", errors="ignore"))
    lines = text.split("\n")
    start_idx = None
    end_idx = None
    for idx, line in enumerate(lines):
        if start_idx is None and line.strip().startswith("VAR_GLOBAL"):
            start_idx = idx
            continue
        if start_idx is not None and line.strip() == "END_VAR":
            end_idx = idx
            break
    if start_idx is None or end_idx is None:
        raise ValueError(f"No VAR_GLOBAL section found in {source_path}")
    return "\n".join(lines[start_idx + 1 : end_idx]).rstrip()


def slice_between_markers(text: str, start_marker: str, end_marker: str | None = None) -> str:
    start_index = text.find(start_marker)
    if start_index < 0:
        return ""
    end_index = len(text) if end_marker is None else text.find(end_marker, start_index)
    if end_index < 0:
        end_index = len(text)
    return text[start_index:end_index].rstrip()


def compact_section(text: str) -> str:
    compacted: list[str] = []
    previous_blank = False
    for line in text.split("\n"):
        is_blank = not line.strip()
        if is_blank and previous_blank:
            continue
        compacted.append(line.rstrip())
        previous_blank = is_blank
    return "\n".join(compacted).strip()


def extract_named_assignments(section_text: str, allowed_names: tuple[str, ...]) -> list[str]:
    lines: list[str] = []
    allowed_prefixes = tuple(f"{name} :" for name in allowed_names)
    for line in section_text.split("\n"):
        if line.strip().startswith(allowed_prefixes):
            lines.append(line.rstrip())
    return lines


def build_process_only_constants(constants_body: str) -> str:
    sections: list[str] = []
    framework_section = slice_between_markers(
        constants_body, "(* ========== Framework ========== *)", "(* ========== Logger ========== *)"
    )
    sections.append(compact_section(framework_section))
    logger_lines = extract_named_assignments(
        constants_body,
        (
            "LOG_MAX_SIZE",
            "defaultLogLevel",
            "defaultLogSuppressDuration",
            "defaultLogSuppressDuplicates",
            "LOG_SOURCE_LIST_MAX_SIZE",
        ),
    )
    if logger_lines:
        sections.append(compact_section("(* ========== Logger ========== *)\n\n" + "\n".join(logger_lines)))
    signal_section = slice_between_markers(
        constants_body, "(* ========== Signal Management ========== *)", "(* ========== Device Config Management ========== *)"
    )
    sections.append(compact_section(signal_section))
    device_config_section = slice_between_markers(constants_body, "(* ========== Device Config Management ========== *)")
    sections.append(compact_section(device_config_section))
    return "\n\n".join(section for section in sections if section)


def build_process_only_globals(globals_body: str) -> str:
    kept_lines: list[str] = []
    for line in globals_body.split("\n"):
        stripped = line.strip()
        if not stripped:
            kept_lines.append(line)
            continue
        if stripped.startswith("(* Timing generation"):
            kept_lines.append(line)
            continue
        if stripped.startswith("(*") and any(
            marker in stripped
            for marker in (
                "Framework args.",
                "All device configs loaded",
                "Facade for managing devices and logical parameters.",
            )
        ):
            kept_lines.append(line)
            continue
        if stripped.startswith(
            (
                "clks :",
                "enable :",
                "init :",
                "fault, error, commError, reset, autoReset :",
                "allConfigLoaded :",
                "logSourceList :",
                "logSourceListSize :",
                "retryCount, retryTime :",
                "isPrimary :",
                "heartbeat :",
                "dev : DeviceFacade;",
            )
        ):
            kept_lines.append(line)
    return compact_section("\n".join(kept_lines))


def indent_text(text: str, prefix: str) -> str:
    return "\n".join((prefix + line) if line else "" for line in text.split("\n"))


def write_ax_configuration(source_root: Path, target_root: Path) -> None:
    src_root = target_root.parent
    configuration_path = src_root / "configuration.st"
    constants_body = build_process_only_constants(
        extract_global_section(source_root / "framework/src/main/resources/MoquiConf.st")
    )
    globals_body = build_process_only_globals(
        extract_global_section(source_root / "framework/src/main/org/moqui/context/ec.st")
    )
    configuration_text = (
        "CONFIGURATION moqui\n"
        "    VAR_GLOBAL CONSTANT\n"
        f"{indent_text(constants_body, '        ')}\n"
        "    END_VAR\n\n"
        "    VAR_GLOBAL\n"
        f"{indent_text(globals_body, '        ')}\n"
        "    END_VAR\n\n"
        "    TASK StartTask(INTERVAL := T#10ms, PRIORITY := 1);\n"
        "    TASK TestTask(INTERVAL := T#10ms, PRIORITY := 2);\n"
        "    PROGRAM MoquiStartInstance WITH StartTask : MoquiStart;\n"
        "    PROGRAM HvacTestSuiteInstance WITH TestTask : HvacTestSuite;\n"
        "END_CONFIGURATION\n"
    )
    configuration_text = re.sub(r"(:\s*UINT\s*:=\s*)(\d+)(\s*;)", r"\1UINT#\2\3", configuration_text)
    configuration_text = configuration_text.replace("LogLevel.Debug", "LogLevel#Debug")
    configuration_path.write_text(configuration_text, encoding="utf-8", newline="\n")


def stage_tree(
    source_root: Path,
    target_root: Path,
    legacy_preserve_root: Path,
    profile: str,
    manual_preserve_root: Path | None = None,
) -> tuple[int, int, dict[str, list[str]]]:
    enum_type_names = collect_local_enum_type_names(source_root)
    preserved_assets = collect_target_assets(target_root)
    policy = POLICIES[profile]
    # Search order: src-manual (authoritative AX overrides) -> current target -> legacy location.
    search_roots: list[Path] = []
    if manual_preserve_root is not None and manual_preserve_root.exists():
        search_roots.append(manual_preserve_root)
    search_roots.append(target_root)
    if legacy_preserve_root.exists():
        search_roots.append(legacy_preserve_root)
    preserved_overrides = collect_preserved_manual_overrides(search_roots, policy.manual_override_stems)
    clean_target_root(target_root)
    restore_target_assets(target_root, preserved_assets)
    write_ax_configuration(source_root, target_root)

    staged_files = 0
    skipped_files = 0
    staged_relative_paths: set[Path] = set()
    transformation_report: dict[str, list[str]] = {}
    for source_path in sorted(source_root.rglob("*")):
        if not source_path.is_file():
            continue
        relative_path = source_path.relative_to(source_root)
        if not should_include(relative_path, profile):
            skipped_files += 1
            continue

        target_path = target_root / relative_path.with_suffix(".st")
        target_path.parent.mkdir(parents=True, exist_ok=True)

        preserved_text = preserved_overrides.get(relative_path.with_suffix(".st"))
        if preserved_text is not None:
            target_path.write_text(normalize_line_endings(preserved_text), encoding="utf-8", newline="\n")
        else:
            converted, applied = convert_text(relative_path, source_path.read_text(encoding="utf-8", errors="ignore"), enum_type_names)
            target_path.write_text(converted, encoding="utf-8", newline="\n")
            transformation_report[relative_path.as_posix()] = applied
        staged_files += 1
        staged_relative_paths.add(relative_path.with_suffix(".st"))

    for relative_path, preserved_text in preserved_overrides.items():
        if relative_path in staged_relative_paths:
            continue
        if relative_path.with_suffix("") not in policy.manual_override_stems:
            continue
        target_path = target_root / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(normalize_line_endings(preserved_text), encoding="utf-8", newline="\n")
        staged_files += 1

    return staged_files, skipped_files, transformation_report


def apply_profile_apax_config(profile: str, ax_root: Path) -> None:
    """Overwrite apax.yml with the profile-specific template."""
    template = APAX_TEMPLATE_BY_PROFILE.get(profile)
    if template is None or not template.exists():
        return
    dest = ax_root / "apax.yml"
    dest.write_text(template.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")


def main() -> None:
    args = parse_args()
    source_root = Path(args.source_root).resolve()
    target_root = Path(args.target_root).resolve()
    legacy_preserve_root = Path(args.legacy_preserve_root).resolve()
    ax_root = DEFAULT_SIMATIC_AX_ROOT

    apply_profile_apax_config(args.profile, ax_root)
    manual_preserve_root = DEFAULT_MANUAL_PRESERVE_ROOT
    staged_files, skipped_files, transformation_report = stage_tree(
        source_root, target_root, legacy_preserve_root, args.profile, manual_preserve_root
    )
    report_path = target_root.parent.parent / "docs" / "staging-transformations.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_lines = [
        "# AX staging transformations",
        "",
        f"Profile: `{args.profile}`",
        "",
        "Each generated file lists only the transformations actually applied.",
        "Manual AX overrides are preserved and are not rewritten.",
        "",
    ]
    for relative, applied in sorted(transformation_report.items()):
        labels = ", ".join(f"`{item}`" for item in applied) if applied else "none"
        report_lines.append(f"- `{relative}`: {labels}")
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8", newline="\n")

    print("Prepared official AX source tree.")
    print(f"Source root : {source_root}")
    print(f"Target root : {target_root}")
    print(f"Profile     : {args.profile}")
    print(f"Staged files: {staged_files}")
    print(f"Skipped files: {skipped_files}")


if __name__ == "__main__":
    main()

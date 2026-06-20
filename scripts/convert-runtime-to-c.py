#!/usr/bin/env python3
"""
Bootstrap transpiler: IEC61131-3 Structured Text -> MISRA-C skeleton for ESP-IDF.

The generated C is intentionally a first-pass skeleton. Files that have been
hand-ported are listed in PRESERVE_C_STEMS; those are copied verbatim from
--manual-preserve-root instead of being regenerated. Everything else gets a
fresh transpiler stub to accelerate initial porting.

Output mirrors the source tree hierarchy under --target-dir (not flat).
"""

import argparse
import re
import shutil
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent

DEFAULT_SOURCE_DIR = REPO_ROOT / "iec61131" / "moqui"
DEFAULT_TARGET_DIR = REPO_ROOT / "iot-firmware" / "components" / "moqui"
DEFAULT_MANUAL_PRESERVE_ROOT = REPO_ROOT / "iot-firmware" / "src-manual"

# Relative stems (no extension, relative to source/target root) whose
# hand-maintained MISRA-C implementations live in src-manual/ and must
# never be overwritten by the transpiler.
PRESERVE_C_STEMS: frozenset[Path] = frozenset({
    Path("framework/src/main/org/moqui/device/Actuator"),
    Path("framework/src/main/org/moqui/device/ActuatorGroup"),
    Path("framework/src/main/org/moqui/util/ClockGeneration"),
    Path("framework/src/main/org/moqui/device/DeviceConfigCmds"),
    Path("framework/src/main/org/moqui/device/DeviceConfigMgmt"),
    Path("framework/src/main/org/moqui/device/EdgeTrigStatusMgr"),
    Path("framework/src/main/org/moqui/util/IIRFilter"),
    Path("framework/src/main/org/moqui/device/LevelCtrlStatusMgr"),
    Path("framework/src/main/org/moqui/context/LoggerFacade"),
    Path("framework/src/main/org/moqui/util/MeanFilter"),
    Path("framework/src/main/org/moqui/mqtt/MqttLogAppender"),
    Path("framework/src/main/org/moqui/diagnostics/NetworkDiagnostics"),
    Path("runtime/component/mantle-hvac/src/main/org/moqui/device/InputSignalUpdate"),
    Path("runtime/component/mantle-hvac/src/main/org/moqui/device/OutputSignalUpdate"),
    Path("framework/src/main/org/moqui/device/ProcessPid"),
    Path("framework/src/main/org/moqui/diagnostics/RemoteIoModuleDiagnostics"),
    Path("framework/src/main/org/moqui/diagnostics/SignalMgmt"),
    Path("framework/src/main/org/moqui/util/SShapedFunc"),
    Path("runtime/component/mantle-hvac/src/main/org/moqui/device/AirDistributionController"),
    Path("runtime/component/mantle-hvac/src/main/org/moqui/device/DeviceDiagnostics"),
    Path("runtime/component/mantle-hvac/src/main/org/moqui/device/DeviceManager"),
    Path("runtime/component/mantle-hvac/src/main/org/moqui/util/json/JsonToParametersMapper"),
    Path("runtime/component/mantle-hvac/src/main/mantle/hvac/Main"),
    Path("runtime/component/mantle-hvac/src/main/mantle/hvac/MainRuleEngine"),
    Path("runtime/component/mantle-hvac/src/main/org/moqui/util/json/ParametersToJsonMapper"),
})

# --- Type mappings ---
TYPE_MAP = {
    "REAL":   "float",
    "BOOL":   "bool",
    "INT":    "int16_t",
    "UINT":   "uint16_t",
    "DINT":   "int32_t",
    "UDINT":  "uint32_t",
    "LINT":   "int64_t",
    "ULINT":  "uint64_t",
    "BYTE":   "uint8_t",
    "WORD":   "uint16_t",
    "DWORD":  "uint32_t",
    "LWORD":  "uint64_t",
    "STRING": "char *",
    "TIME":   "uint32_t",
    "LREAL":  "double",
}

SYNTAX_REPLACEMENTS = [
    (re.compile(r":="),                                              "="),
    (re.compile(r"(?i)\bIF\b\s+(.+?)\s+\bTHEN\b"),                 r"if (\1) {"),
    (re.compile(r"(?i)\bELSIF\b\s+(.+?)\s+\bTHEN\b"),              r"} else if (\1) {"),
    (re.compile(r"(?i)\bELSE\b"),                                   r"} else {"),
    (re.compile(r"(?i)\bEND_IF\b;?"),                               r"}"),
    (re.compile(r"(?i)\bAND\b"),                                    "&&"),
    (re.compile(r"(?i)\bOR\b"),                                     "||"),
    (re.compile(r"(?i)\bNOT\b"),                                    "!"),
    (re.compile(r"(?i)\bTRUE\b"),                                   "true"),
    (re.compile(r"(?i)\bFALSE\b"),                                  "false"),
    (re.compile(r"(?i)\bRETURN\b;"),                                "return;"),
    (re.compile(r"\(\*"),                                           "/*"),
    (re.compile(r"\*\)"),                                           "*/"),
]


def map_type(st_type: str) -> str:
    return TYPE_MAP.get(st_type.strip().upper(), st_type.strip())


def transpile_logic(st_logic: str) -> str:
    result = st_logic
    for pattern, replacement in SYNTAX_REPLACEMENTS:
        result = pattern.sub(replacement, result)
    return result


def extract_variables(block: str) -> list[tuple[str, str]]:
    variables: list[tuple[str, str]] = []
    var_blocks = re.findall(
        r"(?i)\bVAR(?:_INPUT|_OUTPUT|_IN_OUT)?\b(.*?)\bEND_VAR\b", block, re.DOTALL
    )
    for v_block in var_blocks:
        lines = re.findall(
            r"(?m)^\s*([a-zA-Z0-9_]+)\s*:\s*([a-zA-Z0-9_]+)(?:\s*:=\s*[^;]+)?\s*;",
            v_block,
        )
        for var_name, var_type in lines:
            variables.append((var_name, map_type(var_type)))
    return variables


def parse_st_file(filepath: Path) -> dict:
    content = filepath.read_text(encoding="utf-8", errors="ignore")
    parsed: dict = {"enums": [], "structs": [], "function_blocks": []}

    # TYPE ... END_TYPE blocks
    for t_name, t_body in re.findall(
        r"(?i)\bTYPE\s+([a-zA-Z0-9_]+)\s*:\s*(.*?)\bEND_TYPE\b", content, re.DOTALL
    ):
        if "STRUCT" in t_body.upper():
            fields = [
                (v, map_type(t))
                for v, t in re.findall(
                    r"(?m)^\s*([a-zA-Z0-9_]+)\s*:\s*([a-zA-Z0-9_]+)\s*;", t_body
                )
            ]
            parsed["structs"].append({"name": t_name, "fields": fields})
        elif "(" in t_body:
            m = re.search(r"\((.*?)\)", t_body, re.DOTALL)
            if m:
                members = [x.strip() for x in m.group(1).split(",") if x.strip()]
                parsed["enums"].append({"name": t_name, "members": members})

    # FUNCTION_BLOCK ... END_FUNCTION_BLOCK
    for fb_name, fb_body in re.findall(
        r"(?i)\bFUNCTION_BLOCK\s+([a-zA-Z0-9_]+)(.*?)(?:\bEND_FUNCTION_BLOCK\b)",
        content,
        re.DOTALL,
    ):
        variables = extract_variables(fb_body)
        last_end_var = fb_body.upper().rfind("END_VAR")
        logic_raw = fb_body[last_end_var + 7:].strip() if last_end_var != -1 else fb_body.strip()
        parsed["function_blocks"].append(
            {"name": fb_name, "variables": variables, "logic": transpile_logic(logic_raw)}
        )

    return parsed


def generate_h_file(parsed: dict, base_name: str) -> str:
    guard = f"{base_name.upper()}_H"
    lines = [f"#ifndef {guard}", f"#define {guard}", "", "#include <stdint.h>", "#include <stdbool.h>", ""]
    for enum in parsed["enums"]:
        lines += [f"typedef enum {{"] + [f"    {m}," for m in enum["members"]] + [f"}} {enum['name']};", ""]
    for struct in parsed["structs"]:
        lines += [f"typedef struct {{"] + [f"    {t} {n};" for n, t in struct["fields"]] + [f"}} {struct['name']};", ""]
    for fb in parsed["function_blocks"]:
        lines += (
            [f"typedef struct {{"]
            + [f"    {t} {n};" for n, t in fb["variables"]]
            + [f"}} {fb['name']}_DB;", "", f"void {fb['name']}_Update({fb['name']}_DB *instance);", ""]
        )
    lines.append(f"#endif /* {guard} */")
    return "\n".join(lines) + "\n"


def generate_c_file(parsed: dict, base_name: str) -> str:
    lines = [f'#include "{base_name}.h"', ""]
    for fb in parsed["function_blocks"]:
        lines.append(f"void {fb['name']}_Update({fb['name']}_DB *instance) {{")
        for logic_line in fb["logic"].split("\n"):
            lines.append(f"    {logic_line}")
        lines += [f"}}", ""]
    return "\n".join(lines)


def collect_preserved_manual_overrides(
    manual_preserve_root: Path | None,
    target_root: Path,
) -> dict[Path, dict[str, str]]:
    """
    Return {relative_stem: {".c": content, ".h": content}} for each stem in
    PRESERVE_C_STEMS. Search order: src-manual/ first (authoritative), then
    existing target (files already hand-edited in place).
    """
    search_roots = []
    if manual_preserve_root and manual_preserve_root.exists():
        search_roots.append(manual_preserve_root)
    if target_root.exists():
        search_roots.append(target_root)

    preserved: dict[Path, dict[str, str]] = {}
    for stem in PRESERVE_C_STEMS:
        for root in search_roots:
            found: dict[str, str] = {}
            for ext in (".c", ".h"):
                candidate = root / stem.with_suffix(ext)
                if candidate.is_file():
                    found[ext] = candidate.read_text(encoding="utf-8", errors="ignore")
            if found:
                preserved[stem] = found
                break
    return preserved


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bootstrap-transpile IEC61131 ST to MISRA-C skeletons for ESP-IDF."
    )
    parser.add_argument(
        "--source-dir",
        default=str(DEFAULT_SOURCE_DIR),
        help="Root of the IEC61131 source tree (default: iec61131/moqui).",
    )
    parser.add_argument(
        "--target-dir",
        default=str(DEFAULT_TARGET_DIR),
        help="Root of the C output tree (default: iot-firmware/components/moqui).",
    )
    parser.add_argument(
        "--manual-preserve-root",
        default=str(DEFAULT_MANUAL_PRESERVE_ROOT),
        help="Directory with authoritative hand-maintained C files (default: iot-firmware/src-manual).",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Wipe target tree before generating (skips preserved stems).",
    )
    args = parser.parse_args()

    source_dir = Path(args.source_dir)
    target_dir = Path(args.target_dir)
    manual_preserve_root = Path(args.manual_preserve_root)

    preserved = collect_preserved_manual_overrides(manual_preserve_root, target_dir)

    if args.clean:
        if target_dir.exists():
            shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    print(f"Transpiling  : {source_dir}")
    print(f"Target       : {target_dir}")
    print(f"Manual root  : {manual_preserve_root}")
    print(f"Preserved    : {len(preserved)} stems from src-manual")
    print()

    transpiled = preserved_count = skipped = 0

    for st_file in sorted(source_dir.rglob("*.st")):
        relative_stem = st_file.relative_to(source_dir).with_suffix("")

        if relative_stem in PRESERVE_C_STEMS:
            # Write the authoritative hand-maintained version.
            stem_files = preserved.get(relative_stem, {})
            if stem_files:
                for ext, content in stem_files.items():
                    out_path = target_dir / relative_stem.with_suffix(ext)
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    out_path.write_text(content, encoding="utf-8")
                print(f"  preserved : {relative_stem}")
                preserved_count += 1
            else:
                print(f"  WARN: {relative_stem} in PRESERVE_C_STEMS but not found in src-manual or target")
                skipped += 1
            continue

        parsed = parse_st_file(st_file)
        if not parsed["enums"] and not parsed["structs"] and not parsed["function_blocks"]:
            skipped += 1
            continue

        h_content = generate_h_file(parsed, st_file.stem)
        c_content = generate_c_file(parsed, st_file.stem)

        out_dir = target_dir / relative_stem.parent
        out_dir.mkdir(parents=True, exist_ok=True)

        (out_dir / f"{st_file.stem}.h").write_text(h_content, encoding="utf-8")
        if parsed["function_blocks"]:
            (out_dir / f"{st_file.stem}.c").write_text(c_content, encoding="utf-8")

        print(f"  transpiled: {relative_stem}")
        transpiled += 1

    print()
    print(f"Done — transpiled: {transpiled}, preserved: {preserved_count}, skipped (empty): {skipped}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Export CODESYS txtrecipe files into a compact AX runtime recipe format.

Input:
  <configName>.<configType>.txtrecipe

Output:
  index.csv
  recipe-schema.csv
  <configName>.axrecipe

The AX runtime payload uses compact rows:

    <id>;<type>;<value>

where:
  - id   : stable numeric parameter identifier
  - type : exact IEC-oriented type tag expected by the AX runtime parser
  - value: normalized scalar value

This keeps the CODESYS `.txtrecipe` format as engineering/intermediate input,
while generating a PLC-friendly runtime format that Camel can later emit
directly without preserving symbolic `dev.path:=value` strings.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


# None entries are reserved (removed industrial fields) — they consume an ID slot
# so that remaining IDs stay in sync with the CASE statement in DeviceConfigCmds.st.
TOP_LEVEL_SCHEMA: list[tuple[str | None, str | None]] = [
    ("dev.tempSetpoint",           "REAL"),   # 1
    ("dev.tempHysteresis",         "REAL"),   # 2
    ("dev.tempMin",                "REAL"),   # 3
    ("dev.tempMax",                "REAL"),   # 4
    ("dev.rhSetpoint",             "REAL"),   # 5
    ("dev.rhHysteresis",           "REAL"),   # 6
    ("dev.rhMin",                  "REAL"),   # 7
    ("dev.rhMax",                  "REAL"),   # 8
    ("dev.airDistributionEnabled", "BOOL"),   # 9
    ("dev.setPointTimeHigh",       "UINT"),   # 10
    ("dev.setPointTimeLow",        "UINT"),   # 11
    (None, None),                             # 12 reserved
    (None, None),                             # 13 reserved
    ("dev.ductTempMin",            "REAL"),   # 14
    ("dev.ductTempMax",            "REAL"),   # 15
    ("dev.ductRhMax",              "REAL"),   # 16
    ("dev.rhControlEnabled",       "BOOL"),   # 17
    ("dev.rhControlOnly",          "BOOL"),   # 18
    (None, None),                             # 19 reserved
    ("dev.airMixingEnabled",       "BOOL"),   # 20
    ("dev.estimatedRuntime",       "UDINT"),  # 21
    ("dev.minRuntime",             "UDINT"),  # 22
    ("dev.estimatedBreakDuration", "UDINT"),  # 23
    ("dev.minBreakDuration",       "UDINT"),  # 24
    ("dev.processEstimatedDuration", "UDINT"), # 25
    ("dev.processMinDuration",     "UDINT"),  # 26
    ("dev.airFlowRef",             "REAL"),   # 27
    ("dev.ahuFanSpeedSetpoint",    "REAL"),   # 28
    ("dev.tempFeedback",           "REAL"),   # 29
    ("dev.rhFeedback",             "REAL"),   # 30
    (None, None),                             # 31 reserved
    (None, None),                             # 32 reserved
    ("dev.ductTempFeedback",       "REAL"),   # 33
    ("dev.ductRhFeedback",         "REAL"),   # 34
]

ACTUATOR_COMPONENTS = (
    "dev.coldGlycolPump",
    "dev.hotGlycolPump",
    "dev.airFlow",
)

ACTUATOR_SUFFIX_SCHEMA: list[tuple[str, str]] = [
    ("actuatorId", "STRING"),
    ("actuatorName", "STRING"),
    ("actuationType", "INT"),
    ("feedbackType", "INT"),
    ("model", "INT"),
    ("enableTime", "UINT"),
    ("disableTime", "UINT"),
    ("diagnosticsEnable", "BOOL"),
]

PID_COMPONENTS = (
    "dev.coldGlycolValve",
    "dev.hotGlycolValve",
    "dev.ahuFan",
)

PID_SUFFIX_SCHEMA: list[tuple[str, str]] = [
    ("controlSystemId", "STRING"),
    ("controlSystemName", "STRING"),
    ("gain", "REAL"),
    ("integrationTime", "REAL"),
    ("derivationTime", "REAL"),
    ("setpointMin", "REAL"),
    ("setpointMax", "REAL"),
    ("outputMin", "REAL"),
    ("outputMax", "REAL"),
    ("atSetpointHysteresis", "REAL"),
    ("tickTime", "TIME"),
]


def build_schema() -> list[tuple[int, str, str]]:
    rows: list[tuple[int, str, str]] = []
    next_id = 1

    def add(path: str, type_tag: str) -> None:
        nonlocal next_id
        rows.append((next_id, path, type_tag))
        next_id += 1

    for path, type_tag in TOP_LEVEL_SCHEMA:
        if path is None:
            next_id += 1  # consume reserved ID slot without emitting a schema row
        else:
            add(path, type_tag)

    for component in ACTUATOR_COMPONENTS:
        for suffix, type_tag in ACTUATOR_SUFFIX_SCHEMA:
            add(f"{component}.{suffix}", type_tag)

    for component in PID_COMPONENTS:
        for suffix, type_tag in PID_SUFFIX_SCHEMA:
            add(f"{component}.{suffix}", type_tag)

    return rows


SCHEMA_ROWS = build_schema()
SCHEMA_BY_PATH = {path: (param_id, type_tag) for param_id, path, type_tag in SCHEMA_ROWS}


def parse_recipe_filename(path: Path) -> tuple[str, str]:
    parts = path.name.split(".")
    if len(parts) < 3 or parts[-1] != "txtrecipe":
        raise ValueError(f"Unsupported recipe file name: {path.name}")
    config_type = parts[-2]
    config_name = ".".join(parts[:-2])
    if not config_name or not config_type:
        raise ValueError(f"Invalid recipe file name: {path.name}")
    return config_name, config_type


def normalize_scalar_value(type_tag: str, raw_value: str) -> str:
    value = raw_value.strip()
    if type_tag == "STRING":
        if len(value) >= 2 and value[0] == "'" and value[-1] == "'":
            return value[1:-1]
        return value
    return value


def parse_txtrecipe(text: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for raw_line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        if ":=" not in line:
            raise ValueError(f"Invalid txtrecipe line: {raw_line!r}")
        key, value = line.split(":=", 1)
        key = key.strip()
        value = value.strip()
        if key not in SCHEMA_BY_PATH:
            raise ValueError(f"Unsupported AX recipe key: {key}")
        pairs.append((key, value))
    return pairs


def export_recipe_payload(text: str) -> str:
    pairs = parse_txtrecipe(text)
    lines: list[str] = []
    for key, raw_value in pairs:
        param_id, type_tag = SCHEMA_BY_PATH[key]
        value = normalize_scalar_value(type_tag, raw_value)
        lines.append(f"{param_id};{type_tag};{value}")
    return "\n".join(lines) + "\n"


def write_schema(output_dir: Path) -> None:
    schema_path = output_dir / "recipe-schema.csv"
    with schema_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "path", "type"])
        writer.writeheader()
        for param_id, path, type_tag in SCHEMA_ROWS:
            writer.writerow({"id": param_id, "path": path, "type": type_tag})


def export_recipes(source_dir: Path, output_dir: Path) -> None:
    recipes = sorted(source_dir.glob("*.txtrecipe"))
    output_dir.mkdir(parents=True, exist_ok=True)
    write_schema(output_dir)

    rows: list[dict[str, str]] = []
    for recipe_path in recipes:
        try:
            config_name, config_type = parse_recipe_filename(recipe_path)
        except ValueError:
            continue
        runtime_name = f"{config_name}.axrecipe"
        runtime_path = output_dir / runtime_name
        runtime_path.write_text(
            export_recipe_payload(recipe_path.read_text(encoding="utf-8")),
            encoding="utf-8",
            newline="\n",
        )
        rows.append(
            {
                "name": config_name,
                "configType": config_type,
                "fileName": runtime_name,
            }
        )

    index_path = output_dir / "index.csv"
    with index_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "configType", "fileName"])
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export CODESYS txtrecipes into compact AX runtime recipe files.")
    parser.add_argument(
        "--source-dir",
        default="moqui-plc/iec61131/moqui/runtime/component/mantle-hvac/data",
        help="Directory containing *.txtrecipe files.",
    )
    parser.add_argument(
        "--output-dir",
        default="moqui-plc/simatic-ax/src/moqui/runtime/component/mantle-hvac/data",
        help="Directory where index.csv, recipe-schema.csv and *.axrecipe files will be written.",
    )
    args = parser.parse_args()

    export_recipes(Path(args.source_dir), Path(args.output_dir))


if __name__ == "__main__":
    main()

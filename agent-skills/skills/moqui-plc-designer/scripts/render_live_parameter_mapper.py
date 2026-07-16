#!/usr/bin/env python3
"""Generate the Application-specific JsonToParametersMapper from an approved whitelist."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from render_device_catalog_from_seed import (
    field_name_for_parameter,
    parameter_type_to_iec,
    parse_seed_files,
    subtree_device_ids,
)

PLANT_SCRIPT_DIR = Path(__file__).resolve().parents[2] / "moqui-plant-designer" / "scripts"
if str(PLANT_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(PLANT_SCRIPT_DIR))

from survey_validation import load_upstream_survey_model


MQTT_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")


def value_expression(iec_type: str) -> str:
    if iec_type == "BOOL":
        return "jsonValue.value.xValue"
    if iec_type == "STRING":
        return "LEFT(TO_STRING(jsonValue.value.wsValue), 255)"
    if iec_type == "TIME":
        return "TO_TIME(TO_DINT(jsonValue.value.lrValue))"
    if iec_type in {"REAL", "LREAL", "INT", "UINT", "DINT", "UDINT", "BYTE", "WORD", "DWORD", "LWORD"}:
        return f"TO_{iec_type}(jsonValue.value.lrValue)"
    raise SystemExit(f"Live update does not support generated IEC type {iec_type}.")


def render_mapper(seed_path: Path, root_device_id: str, session_dir: Path) -> tuple[str, list[str]]:
    devices, physical, pdefs, parameters, _, _, _, _ = parse_seed_files([seed_path])
    if root_device_id not in devices:
        raise SystemExit(f"Mapper root Device {root_device_id} not found in seed.")
    scope = subtree_device_ids(root_device_id, devices)
    whitelist = [row for row in load_upstream_survey_model(session_dir)["live_parameters"] if row["parameter_id"]]
    branches: list[str] = []
    mapped_ids: list[str] = []
    for row in whitelist:
        mqtt_key = row["mqtt_key"]
        if not MQTT_KEY.fullmatch(mqtt_key):
            raise SystemExit(f"Live parameter mqtt_key is not a safe scalar JSON key: {mqtt_key}")
        parameter = parameters.get(row["parameter_id"])
        if not parameter or parameter.device_id not in scope:
            continue
        pdef = pdefs.get(parameter.parameter_def_id)
        if not pdef:
            raise SystemExit(f"Live parameter {parameter.parameter_id} references missing ParameterDef {parameter.parameter_def_id}.")
        field_name = field_name_for_parameter(root_device_id, parameter.device_id, physical, parameter, pdef)
        iec_type = parameter_type_to_iec(pdef.parameter_type_enum_id)
        keyword = "IF" if not branches else "ELSIF"
        branches.append(
            f'\t{keyword} jsonKey = "{mqtt_key}" THEN\n'
            f"\t\tdev.{field_name} := {value_expression(iec_type)}; "
            f"(* {parameter.parameter_id} *)"
        )
        mapped_ids.append(parameter.parameter_id)
    body = "\n".join(branches)
    if branches:
        body += "\n\tEND_IF;"
    else:
        body = "\t(* This Application has no approved live-update parameters; unknown keys are ignored. *)"
    text = f'''FUNCTION_BLOCK JsonToParametersMapper
\tVAR_EXTERNAL
\t\tdev : DeviceFacade;
\tEND_VAR
\tVAR_INPUT
\t\tjsonKey : WSTRING(255) := "";
\t\tjsonValue : JSON.JSONElement;
\tEND_VAR

\tIF jsonKey = "" THEN RETURN; END_IF;

{body}
\tEND_FUNCTION_BLOCK
'''
    return text, mapped_ids


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate an Application-specific MQTT live-parameter mapper")
    parser.add_argument("seed", type=Path)
    parser.add_argument("--device-id", required=True, help="Application root DeviceGroup")
    parser.add_argument("--session-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    text, mapped = render_mapper(args.seed.resolve(), args.device_id, args.session_dir.resolve())
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")
    print(f"Rendered JsonToParametersMapper with {len(mapped)} approved parameter(s) to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

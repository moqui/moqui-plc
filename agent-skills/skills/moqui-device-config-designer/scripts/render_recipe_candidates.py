#!/usr/bin/env python3
#
# This software is in the public domain under CC0 1.0 Universal plus a
# Grant of Patent License.
#
# To the extent possible under law, the author(s) have dedicated all
# copyright and related and neighboring rights to this software to the
# public domain worldwide. This software is distributed without any
# warranty.
#
# You should have received a copy of the CC0 Public Domain Dedication
# along with this software (see the LICENSE.md file). If not, see
# <http://creativecommons.org/publicdomain/zero/1.0/>.

"""
Render candidate txtrecipe lines from a DeviceFacade.dut file.

The script treats DeviceFacade as the primary source of truth for recipe structure.
It derives:
  - top-level configurable logical parameters
  - configuration fields for instantiated atomic FBs

It intentionally excludes feedback fields, runtime fields, computed predicates,
request flags, FSM status, and signal-management internals.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


ATOMIC_FB_FIELDS = {
    "Actuator": [
        ("actuatorId", "STRING"),
        ("actuatorName", "STRING"),
        ("actuationType", "UINT"),
        ("feedbackType", "UINT"),
        ("model", "UINT"),
        ("operationType", "UINT"),
        ("enableTime", "UINT"),
        ("disableTime", "UINT"),
        ("enablePreset", "BOOL"),
        ("diagnosticsEnable", "BOOL"),
    ],
    "ActuatorGroup": [
        ("actuatorGroupId", "STRING"),
        ("actuatorGroupName", "STRING"),
        ("actuatorNum", "UINT"),
        ("minRunning", "UINT"),
        ("maxRunning", "UINT"),
        ("demandSetpoint", "REAL"),
        ("startDelay", "TIME"),
        ("stopDelay", "TIME"),
        ("autochange", "UINT"),
        ("autochangeInterval", "TIME"),
        ("maxWearImbalance", "REAL"),
        ("autochangeLevel", "REAL"),
        ("autochangeTrigger", "BOOL"),
    ],
    "Axis": [
        ("cmd", "UINT"),
        ("position", "REAL"),
        ("distance", "REAL"),
        ("velocity", "REAL"),
        ("velocityDiff", "REAL"),
        ("acceleration", "REAL"),
        ("deceleration", "REAL"),
        ("jerk", "REAL"),
        ("bufferMode", "UINT"),
        ("direction", "UINT"),
        ("homePosition", "REAL"),
        ("ratioNumerator", "DINT"),
        ("ratioDenominator", "DINT"),
        ("masterSyncPos", "REAL"),
        ("slaveSyncPos", "REAL"),
        ("camVersion", "DWORD"),
        ("masterOffset", "REAL"),
        ("slaveOffset", "REAL"),
        ("phaseShift", "REAL"),
        ("setPositionMode", "BOOL"),
        ("overrideEnable", "BOOL"),
        ("velFactor", "REAL"),
        ("accFactor", "REAL"),
        ("jerkFactor", "REAL"),
        ("jogForward", "BOOL"),
        ("jogBackward", "BOOL"),
        ("touchProbeWindow", "BOOL"),
        ("touchProbeFirst", "REAL"),
        ("touchProbeLast", "REAL"),
    ],
    "AxisGroup": [
        ("axisGroupId", "STRING"),
        ("axisGroupName", "STRING"),
        ("cmd", "UINT"),
        ("velocity", "LREAL"),
        ("acceleration", "LREAL"),
        ("deceleration", "LREAL"),
        ("jerk", "LREAL"),
        ("transitionParameter", "LREAL"),
        ("overrideEnable", "BOOL"),
        ("velFactor", "REAL"),
        ("accFactor", "REAL"),
        ("jerkFactor", "REAL"),
    ],
    "ProcessPid": [
        ("controlSystemId", "STRING"),
        ("controlSystemName", "STRING"),
        ("feedbackMultiplier", "REAL"),
        ("setpoint", "REAL"),
        ("setpointMultiplier", "REAL"),
        ("setpointMin", "REAL"),
        ("setpointMax", "REAL"),
        ("setpointRampType", "UINT"),
        ("setpointIncreaseTime", "TIME"),
        ("setpointDecreaseTime", "TIME"),
        ("setpointFreezeEnable", "BOOL"),
        ("deviationInversion", "BOOL"),
        ("outputMin", "REAL"),
        ("outputMax", "REAL"),
        ("outputFreezeEnable", "BOOL"),
        ("gain", "REAL"),
        ("integrationTime", "REAL"),
        ("derivationTime", "REAL"),
        ("offset", "REAL"),
        ("deadbandRange", "REAL"),
        ("deadbandDelay", "TIME"),
        ("sleepLevel", "REAL"),
        ("sleepDelay", "TIME"),
        ("wakeupDeviation", "REAL"),
        ("wakeupDelay", "TIME"),
        ("sleepBoostLevel", "REAL"),
        ("sleepBoostTime", "TIME"),
        ("trackingMode", "BOOL"),
        ("trackingRef", "REAL"),
        ("tickTime", "TIME"),
        ("setpointEpsilon", "REAL"),
    ],
    "SignalMgmt": [],
}

INCLUDE_SIMPLE_TYPES = {
    "REAL",
    "LREAL",
    "BOOL",
    "UINT",
    "UDINT",
    "DINT",
    "INT",
    "TIME",
    "STRING",
    "WORD",
    "DWORD",
}

EXCLUDE_TOP_LEVEL_NAMES = {
    "status",
    "lastStatus",
    "signalMgmt",
    "processActualDuration",
    "processRemainingDuration",
    "actualRuntime",
    "actualBreakDuration",
    "airMixingActualDuration",
    "airMixingActualBreakDuration",
    "isCompleted",
    "timeBreakEnabled",
}

EXCLUDE_NAME_PREFIXES = (
    "actual",
)

EXCLUDE_NAME_SUFFIXES = (
    "Request",
)

EXCLUDE_SECTION_MARKERS = (
    "Boolean predicates",
    "Main FSM state and transition request/acknowledge commands",
)


@dataclass
class Field:
    name: str
    field_type: str
    section: str


FIELD_RE = re.compile(r"^\s*([A-Za-z_]\w*)\s*:\s*([A-Za-z_]\w*)\b")


def default_value(field_type: str, name: str) -> str:
    if field_type == "STRING":
        return f"'${{{name.upper()}}}'"
    if field_type == "BOOL":
        return "FALSE"
    if field_type == "TIME":
        return "T#0s"
    if field_type in {"REAL", "LREAL"}:
        return "0.0"
    if field_type in {"UINT", "UDINT", "DINT", "INT", "WORD", "DWORD"}:
        return "0"
    return "${VALUE}"


def parse_device_facade(path: Path) -> list[Field]:
    text = path.read_text(encoding="utf-8")
    in_struct = False
    section = ""
    fields: list[Field] = []

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if "TYPE DeviceFacade : STRUCT" in line:
            in_struct = True
            continue
        if in_struct and "END_STRUCT END_TYPE" in line:
            break
        if not in_struct:
            continue

        stripped = line.strip()
        if stripped.startswith("(*") and stripped.endswith("*)"):
            comment = stripped[2:-2].strip()
            if comment:
                section = comment
            continue

        match = FIELD_RE.match(line)
        if match:
            fields.append(Field(match.group(1), match.group(2), section))

    return fields


def include_top_level(field: Field) -> bool:
    if field.field_type not in INCLUDE_SIMPLE_TYPES:
        return False
    if field.name in EXCLUDE_TOP_LEVEL_NAMES:
        return False
    if any(field.name.startswith(prefix) for prefix in EXCLUDE_NAME_PREFIXES):
        return False
    if any(field.name.endswith(suffix) for suffix in EXCLUDE_NAME_SUFFIXES):
        return False
    if any(marker in field.section for marker in EXCLUDE_SECTION_MARKERS):
        return False
    if "Feedback" in field.name:
        return False
    if "Over" in field.name or "Under" in field.name or "InRange" in field.name:
        return False
    if field.name.endswith("AtSetpoint"):
        return False
    return True


def render_recipe(fields: list[Field]) -> list[str]:
    lines: list[str] = []

    for field in fields:
        if include_top_level(field):
            lines.append(f"dev.{field.name}:={default_value(field.field_type, field.name)}")

    for field in fields:
        if field.field_type in ATOMIC_FB_FIELDS:
            for subfield, placeholder_type in ATOMIC_FB_FIELDS[field.field_type]:
                lines.append(
                    f"dev.{field.name}.{subfield}:={default_value(placeholder_type, f'{field.name}_{subfield}')}"
                )

    return lines


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_session(session_dir: Path) -> tuple[Path, dict]:
    session_path = session_dir / "session.json"
    if not session_path.is_file():
        raise SystemExit(f"session.json not found in session directory: {session_dir}")
    return session_path, json.loads(session_path.read_text(encoding="utf-8"))


def infer_component_name(device_facade: Path) -> str:
    parts = list(device_facade.parts)
    if "generated-plc" in parts:
        idx = parts.index("generated-plc")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    parent = device_facade.parent
    return parent.name or "recipe"


def resolve_output_path(args: argparse.Namespace) -> Path | None:
    if args.output:
        return args.output
    if args.session_dir:
        session_path, session = load_session(args.session_dir)
        recipes_dir_name = session.get("paths", {}).get("generatedRecipesDir", "generated-recipes")
        file_name = args.output_name or f"{infer_component_name(args.device_facade)}.txtrecipe"
        return session_path.parent / recipes_dir_name / file_name
    return None


def update_session_metadata(session_dir: Path, output_path: Path) -> None:
    session_path, session = load_session(session_dir)
    rel_output = str(output_path.relative_to(session_dir))
    artifacts = session.setdefault("artifacts", {})
    generated = artifacts.setdefault("generatedRecipes", [])
    if rel_output not in generated:
        generated.append(rel_output)
    session["updatedAt"] = utc_now()
    session["currentStage"] = "config_recipe"
    session["currentSkill"] = "moqui-device-config-designer"
    steps = session.setdefault("steps", {})
    step = steps.setdefault("config_recipe", {"status": "pending", "notes": ""})
    step["status"] = "completed"
    step["notes"] = f"Generated recipe template {output_path.name}"
    session_path.write_text(json.dumps(session, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Render candidate txtrecipe lines from DeviceFacade.dut")
    parser.add_argument("device_facade", type=Path, help="Path to DeviceFacade.dut")
    parser.add_argument("--output", type=Path, help="Output file for the generated txtrecipe")
    parser.add_argument(
        "--session-dir",
        type=Path,
        help="Saved session directory; if provided, default output goes to generated-recipes/ and session.json is updated",
    )
    parser.add_argument(
        "--output-name",
        help="File name to use inside the session generated-recipes/ directory when --session-dir is provided",
    )
    args = parser.parse_args()

    fields = parse_device_facade(args.device_facade)
    lines = render_recipe(fields)
    output_path = resolve_output_path(args)
    if output_path is None:
        for line in lines:
            print(line)
        return 0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if args.session_dir:
        update_session_metadata(args.session_dir.resolve(), output_path.resolve())
    print(f"Wrote recipe candidates to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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
Compose a Moqui seed XML file from reusable seed template fragments.

Spec format:
{
  "includes": ["base", "mqtt", "framework_ec"],
  "variables": {
    "DEVICE_ID": "VIRTUAL_PLC_1",
    ...
  }
}
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

PLANT_SCRIPT_DIR = Path(__file__).resolve().parents[2] / "moqui-plant-designer" / "scripts"
if str(PLANT_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(PLANT_SCRIPT_DIR))

from survey_validation import validate_upstream_surveys


PLACEHOLDER_RE = re.compile(r"\$\{([A-Z0-9_]+)\}")

TEMPLATE_MAP = {
    "base": "base-device-seed-template.xml",
    "digital_sensor": "digital-sensor-seed-template.xml",
    "analog_sensor": "analog-sensor-seed-template.xml",
    "actuator": "actuator-seed-template.xml",
    "actuator_group": "actuator-group-seed-template.xml",
    "process_pid": "process-pid-seed-template.xml",
    "axis": "axis-seed-template.xml",
    "axis_group": "axis-group-seed-template.xml",
    "signal_mgmt": "signal-mgmt-seed-template.xml",
    "device_group": "device-group-seed-template.xml",
    "device_config": "device-config-template.xml",
    "device_config_set": "device-config-set-template.xml",
    "actuator_config": "actuator-device-config-template.xml",
    "actuator_group_config": "actuator-group-device-config-template.xml",
    "process_pid_config": "process-pid-device-config-template.xml",
    "axis_config": "axis-device-config-template.xml",
    "axis_group_config": "axis-group-device-config-template.xml",
    "signal_mgmt_config": "signal-mgmt-device-config-template.xml",
    "mqtt": "mqtt-device-request-seed-template.xml",
    "opcua": "opcua-device-request-seed-template.xml",
    "gateway_wrapper": "gateway-wrapper-request-seed-template.xml",
    "framework_ec": "framework-ec-seed-template.xml",
}


def load_spec(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("Spec must be a JSON object")
    includes = data.get("includes", [])
    variables = data.get("variables", {})
    if not isinstance(includes, list) or not all(isinstance(i, str) for i in includes):
        raise SystemExit("'includes' must be a list of strings")
    if not isinstance(variables, dict) or not all(isinstance(k, str) for k in variables.keys()):
        raise SystemExit("'variables' must be an object with string keys")
    return {"includes": includes, "variables": {str(k): str(v) for k, v in variables.items()}}


def strip_root(template_text: str) -> str:
    lines = template_text.splitlines()
    kept: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("<?xml "):
            continue
        if stripped == '<entity-facade-xml type="seed">':
            continue
        if stripped == "</entity-facade-xml>":
            continue
        kept.append(line)
    return "\n".join(kept).strip() + "\n"


def render_template(template_text: str, variables: dict[str, str]) -> str:
    missing = sorted(set(PLACEHOLDER_RE.findall(template_text)) - set(variables.keys()))
    if missing:
        raise SystemExit("Missing variables for template rendering: " + ", ".join(missing))

    def repl(match: re.Match[str]) -> str:
        return variables[match.group(1)]

    return PLACEHOLDER_RE.sub(repl, template_text)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_session(session_dir: Path) -> tuple[Path, dict]:
    session_path = session_dir / "session.json"
    if not session_path.is_file():
        raise SystemExit(f"session.json not found in session directory: {session_dir}")
    return session_path, json.loads(session_path.read_text(encoding="utf-8"))


def resolve_output_path(args: argparse.Namespace) -> Path:
    if args.output:
        return args.output
    if args.session_dir:
        session_path, session = load_session(args.session_dir)
        seed_data_dir_name = session.get("paths", {}).get("seedDataDir", "seed-data")
        output_name = args.output_name or f"{args.spec.stem}.xml"
        return session_path.parent / seed_data_dir_name / output_name
    raise SystemExit("Provide --output or --session-dir")


def update_session_metadata(session_dir: Path, output_path: Path, spec_path: Path) -> None:
    session_path, session = load_session(session_dir)
    rel_output = str(output_path.relative_to(session_dir))
    artifacts = session.setdefault("artifacts", {})
    seed_artifacts = artifacts.setdefault("seedData", [])
    if rel_output not in seed_artifacts:
        seed_artifacts.append(rel_output)
    session["updatedAt"] = utc_now()
    session["currentStage"] = "seed_design"
    session["currentSkill"] = "moqui-device-seed-designer"
    session["status"] = "needs_review"
    steps = session.setdefault("steps", {})
    seed_step = steps.setdefault("seed_design", {"status": "pending", "notes": ""})
    seed_step["status"] = "generated"
    seed_step["notes"] = f"Generated seed bundle from {spec_path.name}; review against the Moqui model before downstream generation."
    session_path.write_text(json.dumps(session, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Compose a Moqui seed XML bundle from template fragments")
    parser.add_argument("spec", type=Path, help="Path to bundle spec JSON")
    parser.add_argument(
        "--templates-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "references",
        help="Directory containing seed template fragments",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output path for the composed seed XML",
    )
    parser.add_argument(
        "--session-dir",
        type=Path,
        help="Saved session directory; if provided, default output goes to seed-data/ and session.json is updated",
    )
    parser.add_argument(
        "--output-name",
        help="File name to use inside the session seed-data/ directory when --session-dir is provided",
    )
    args = parser.parse_args()

    if args.session_dir:
        validate_upstream_surveys(args.session_dir.resolve())

    spec = load_spec(args.spec)
    includes: list[str] = spec["includes"]
    variables: dict[str, str] = spec["variables"]

    fragments: list[str] = []
    for include in includes:
        template_name = TEMPLATE_MAP.get(include)
        if not template_name:
            raise SystemExit(f"Unknown include '{include}'. Known includes: {', '.join(sorted(TEMPLATE_MAP))}")
        template_path = args.templates_dir / template_name
        template_text = template_path.read_text(encoding="utf-8")
        rendered = render_template(strip_root(template_text), variables)
        fragments.append(rendered.rstrip())

    output = ['<?xml version="1.0" encoding="UTF-8"?>', '<entity-facade-xml type="seed">', ""]
    for idx, fragment in enumerate(fragments):
        output.append(fragment)
        if idx != len(fragments) - 1:
            output.append("")
    output.extend(["", "</entity-facade-xml>", ""])

    output_path = resolve_output_path(args)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(output), encoding="utf-8")
    if args.session_dir:
        update_session_metadata(args.session_dir.resolve(), output_path.resolve(), args.spec.resolve())
    print(f"Wrote seed bundle to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

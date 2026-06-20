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
Render a review checklist for MoquiConf.gvl based on the chosen exposure mode.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SECTIONS = {
    "framework": [
        "retryOnError",
        "minRetryTime",
        "maxRetryCount",
    ],
    "logger": [
        "LOG_MAX_SIZE",
        "defaultLogLevel",
        "LOG_SOURCE_LIST_MAX_SIZE",
        "LOG_JSON_PAYLOAD_MAX_SIZE",
        "JSON_PAYLOAD_MAX_SIZE",
        "JSON_LINE_BREAK",
        "JSON_ELEMENT_LIST_MAX_SIZE",
        "LOG_APPENDER_BATCH_SIZE",
        "logTopic",
        "logAppenderTimeout",
        "moquiCmdsTopic",
        "liveParamsSubTopic",
        "liveParamsSubTimeout",
        "liveParamsPubTopic",
        "liveParamsPubTimeout",
    ],
    "communication": [
        "fieldbus",
    ],
    "modbus": [
        "MODBUS_OVERRANGE",
        "MODBUS_OVERFLOW",
    ],
    "mqtt": [
        "brokerUrl",
        "brokerPort",
        "webSocketUrl",
        "clientId",
        "username",
        "password",
        "sessionExpiryInterval",
        "keepAlive",
        "cleanSession",
        "timeout",
        "pingInterval",
        "maximumPacketSize",
        "communicationMode",
        "mqttVersion",
        "willTopic",
        "willMessage",
        "willRetain",
        "willQoS",
        "willPayloadFormatIndicator",
        "willMessageExpiryInterval",
        "willContentType",
        "willDelayInterval",
        "pubPayloadFormatIndicator",
        "pubMessageExpiryInterval",
        "pubContentType",
        "paramsPubQoS",
        "paramsPubRetain",
        "paramsReDelivery",
        "logPubQoS",
        "logPubRetain",
        "logReDelivery",
        "subscriptionIdentifier",
        "subNoLocalOption",
        "subRetainAsPublished",
        "subRetainHandling",
        "paramsSubQoS",
        "paramsSubFilterMode",
    ],
    "signal_management": [
        "SIGNAL_LIST_MAX_SIZE",
    ],
    "device_config_management": [
        "DEVICE_CONFIG_LIST_MAX_SIZE",
        "defaultConfigType",
        "deviceConfigStoragePath",
        "ACTUATOR_GROUP_MAX_SIZE",
        "AXIS_IN_VELOCITY_TOLERANCE",
    ],
}


def render_section(title: str, fields: list[str]) -> list[str]:
    lines = [f"## {title}", ""]
    lines.extend(f"- `{field}` =" for field in fields)
    lines.append("")
    return lines


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_session(session_dir: Path) -> tuple[Path, dict]:
    session_path = session_dir / "session.json"
    if not session_path.is_file():
        raise SystemExit(f"session.json not found in session directory: {session_dir}")
    return session_path, json.loads(session_path.read_text(encoding="utf-8"))


def resolve_output_path(args: argparse.Namespace) -> Path | None:
    if args.output:
        return args.output
    if args.session_dir:
        session_path, session = load_session(args.session_dir)
        config_dir_name = session.get("paths", {}).get("generatedConfigDir", "generated-config")
        file_name = args.output_name or "moqui-conf-checklist.md"
        return session_path.parent / config_dir_name / file_name
    return None


def update_session_metadata(session_dir: Path, output_path: Path) -> None:
    session_path, session = load_session(session_dir)
    rel_output = str(output_path.relative_to(session_dir))
    artifacts = session.setdefault("artifacts", {})
    generated = artifacts.setdefault("generatedConfig", [])
    if rel_output not in generated:
        generated.append(rel_output)
    session["updatedAt"] = utc_now()
    session["currentStage"] = "plc_framework_config"
    session["currentSkill"] = "moqui-plc-config"
    steps = session.setdefault("steps", {})
    step = steps.setdefault("plc_framework_config", {"status": "pending", "notes": ""})
    step["status"] = "completed"
    step["notes"] = f"Generated MoquiConf checklist {output_path.name}"
    session_path.write_text(json.dumps(session, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a MoquiConf.gvl review checklist")
    parser.add_argument(
        "--exposure-mode",
        choices=["mqtt", "opcua", "both", "none"],
        default="mqtt",
        help="How the PLC exposes data outward",
    )
    parser.add_argument(
        "--fieldbus",
        choices=["modbus", "other"],
        default="modbus",
        help="Whether the internal fieldbus is Modbus-like",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional output file. If omitted, prints to stdout.",
    )
    parser.add_argument(
        "--session-dir",
        type=Path,
        help="Saved session directory; if provided, default output goes to generated-config/ and session.json is updated",
    )
    parser.add_argument(
        "--output-name",
        help="File name to use inside the session generated-config/ directory when --session-dir is provided",
    )
    args = parser.parse_args()

    lines: list[str] = ["# MoquiConf Review Checklist", ""]
    lines.extend(render_section("Framework", SECTIONS["framework"]))
    lines.extend(render_section("Logger", SECTIONS["logger"]))
    lines.extend(render_section("Communication Protocols", SECTIONS["communication"]))

    if args.fieldbus == "modbus":
        lines.extend(render_section("Modbus", SECTIONS["modbus"]))

    if args.exposure_mode in {"mqtt", "both"}:
        lines.extend(render_section("MQTT", SECTIONS["mqtt"]))
    else:
        lines.extend(["## MQTT", "", "- omitted because exposure mode is not MQTT", ""])

    lines.extend(render_section("Signal Management", SECTIONS["signal_management"]))
    lines.extend(render_section("Device Config Management", SECTIONS["device_config_management"]))

    text = "\n".join(lines)
    output_path = resolve_output_path(args)
    if output_path is None:
        print(text)
        return 0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")
    if args.session_dir:
        update_session_metadata(args.session_dir.resolve(), output_path.resolve())
    print(f"Wrote MoquiConf checklist to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

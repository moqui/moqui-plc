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
Render MainStatus/Main/MainRuleEngine skeletons from a Moqui StatusFlow.

This script uses:
  - DeviceData.xml (or another seed XML containing StatusFlow data)
  - the skill templates in references/plc-codegen-templates/

It does not try to invent real transition conditions.
Instead it generates stable skeleton code with placeholders and transition lists.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

PLANT_SCRIPT_DIR = Path(__file__).resolve().parents[2] / "moqui-plant-designer" / "scripts"
if str(PLANT_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(PLANT_SCRIPT_DIR))

from survey_validation import (
    load_upstream_survey_model,
    validate_fsm_surveys,
    validate_upstream_surveys,
)


@dataclass
class StatusItemDef:
    status_id: str
    description: str
    sequence_num: int
    enum_name: str
    is_initial: bool


@dataclass
class TransitionDef:
    from_status_id: str
    to_status_flow_id: str
    to_status_id: str
    transition_name: str
    transition_sequence: int


TAG_STATUS_ITEM = "moqui.basic.StatusItem"
TAG_STATUS_FLOW_ITEM = "moqui.basic.StatusFlowItem"
TAG_STATUS_FLOW_TRANSITION = "moqui.basic.StatusFlowTransition"


def fail_validation(errors: list[str]) -> None:
    raise SystemExit("StatusFlow validation failed:\n- " + "\n- ".join(errors))


def local_name(tag: str) -> str:
    return tag.split("}", 1)[-1]


def normalize_enum_name(status_id: str, description: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "", description)
    if cleaned:
        return cleaned
    fallback = re.sub(r"^[A-Z][a-z]?[a-z]?", "", status_id)
    return fallback or status_id


def normalize_component_name(statusflow_id: str) -> str:
    name = statusflow_id
    for suffix in ("StatusFlow", "Flow"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    return name[:1].lower() + name[1:] if name else "component"


def to_lower_camel(raw: str) -> str:
    chunks = re.findall(r"[A-Za-z0-9]+", raw)
    parts = [
        word
        for chunk in chunks
        for word in re.findall(r"[A-Z]+(?=[A-Z][a-z]|\d|$)|[A-Z]?[a-z]+|\d+", chunk)
    ]
    if not parts:
        return "value"
    return parts[0].lower() + "".join(part[:1].upper() + part[1:] for part in parts[1:])


def st_assignment(row: dict) -> str:
    target = row["target"]
    if "." not in target:
        target = f"dev.{target}"
    suffix = f" (* {row['comment']} *)" if row.get("comment") else ""
    return f"{target} := {row['expression']};{suffix}"


def device_field_name(device: dict) -> str:
    return to_lower_camel(device.get("physical_device_name") or device["device_id"])


def device_control_assignments(device: dict, enabled: bool) -> list[str]:
    field = device_field_name(device)
    model = device["logical_model"]
    value = "TRUE" if enabled else "FALSE"
    inverse = "FALSE" if enabled else "TRUE"
    if model == "Actuator":
        return [f"dev.{field}EnableRequest := {value};", f"dev.{field}DisableRequest := {inverse};"]
    if model == "ActuatorGroup":
        return [f"dev.{field}GroupEnable := {value};", f"dev.{field}GroupDisable := {inverse};"]
    if model == "ProcessPid":
        return [f"dev.{field}Enable := {value};"]
    if model == "Axis":
        return [f"dev.{field}AxisEnable := {value};"]
    if model == "AxisGroup":
        return [f"dev.{field}GroupEnable := {value};"]
    raise SystemExit(
        f"Device {device['device_id']} uses {model}; define explicit output_assignments because no generic enable policy exists."
    )


def devices_in_subsystem(model: dict, subsystem_id: str) -> list[dict]:
    descendants = {subsystem_id}
    changed = True
    while changed:
        changed = False
        for row in model["system_tree"]:
            if row["parent_subsystem_id"] in descendants and row["subsystem_id"] not in descendants:
                descendants.add(row["subsystem_id"])
                changed = True
    return [device for device in model["devices"] if device["parent_subsystem_id"] in descendants]


def render_output_assignments(state: dict, model: dict) -> str:
    device_by_id = {device["device_id"]: device for device in model["devices"]}
    subsystem_ids = {row["subsystem_id"] for row in model["system_tree"]}
    lines: list[str] = []
    seen: set[tuple[str, bool]] = set()
    for action_name, enabled in (("activate", True), ("deactivate", False)):
        action = state[action_name]
        selected: list[dict] = []
        for ref in action["device_groups"]:
            if ref in subsystem_ids:
                selected.extend(devices_in_subsystem(model, ref))
            elif ref in device_by_id:
                selected.append(device_by_id[ref])
        selected.extend(device_by_id[ref] for ref in action["physical_devices"])
        for device in selected:
            key = (device["device_id"], enabled)
            if key in seen:
                continue
            seen.add(key)
            lines.extend(device_control_assignments(device, enabled))
        for request_flag in action["request_flags"]:
            target = request_flag if "." in request_flag else f"dev.{request_flag}"
            lines.append(f"{target} := {'TRUE' if enabled else 'FALSE'};")
    lines.extend(st_assignment(row) for row in state["output_assignments"])
    return "\n        ".join(lines) if lines else "; (* reviewed state with no output assignments *)"


def select_fsm_model(session_dir: Path, statusflow_id: str) -> tuple[dict, dict]:
    upstream = load_upstream_survey_model(session_dir)
    fsm_model = validate_fsm_surveys(session_dir, upstream)
    fsm = next((row for row in fsm_model["fsms"] if row["status_flow_id"] == statusflow_id), None)
    if not fsm:
        raise SystemExit(f"No reviewed FSM survey found for StatusFlow {statusflow_id}.")
    if not fsm["code_generation_approved"]:
        raise SystemExit(f"FSM {fsm['fsm_id']} must set code_generation_approved: true before PLC generation.")
    unreviewed = [state["status_id"] for state in fsm["states"] if not state["outputs_reviewed"]]
    if unreviewed:
        raise SystemExit(f"FSM {fsm['fsm_id']} has unreviewed output functions: {', '.join(unreviewed)}")
    return upstream, fsm


def load_request_map(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("Request map must be a JSON object: {\"Standstill\": \"standbyRequest\", ...}")
    normalized: dict[str, str] = {}
    for key, value in data.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise SystemExit("Request map keys and values must be strings")
        normalized[key] = value
    return normalized


def parse_statusflow(xml_path: Path, statusflow_id: str) -> tuple[list[StatusItemDef], list[TransitionDef]]:
    tree = ET.parse(xml_path)
    root = tree.getroot()

    status_items_by_id: dict[str, dict[str, str]] = {}
    flow_item_initial: dict[str, bool] = {}
    all_flow_items: dict[str, set[str]] = {}
    transitions: list[TransitionDef] = []

    for elem in root.iter():
        tag = local_name(elem.tag)
        if tag == TAG_STATUS_ITEM:
            status_items_by_id[elem.attrib["statusId"]] = elem.attrib
        elif tag == TAG_STATUS_FLOW_ITEM:
            item_flow_id = elem.attrib.get("statusFlowId", "")
            all_flow_items.setdefault(item_flow_id, set()).add(elem.attrib["statusId"])
            if item_flow_id == statusflow_id:
                flow_item_initial[elem.attrib["statusId"]] = elem.attrib.get("isInitial") == "Y"
        elif tag == TAG_STATUS_FLOW_TRANSITION and elem.attrib.get("statusFlowId") == statusflow_id:
            transitions.append(
                TransitionDef(
                    from_status_id=elem.attrib["statusId"],
                    to_status_flow_id=elem.attrib.get("toStatusFlowId", statusflow_id),
                    to_status_id=elem.attrib["toStatusId"],
                    transition_name=elem.attrib.get("transitionName", ""),
                    transition_sequence=int(elem.attrib.get("transitionSequence", "0")),
                )
            )

    errors: list[str] = []
    items: list[StatusItemDef] = []
    for status_id, is_initial in flow_item_initial.items():
        src = status_items_by_id.get(status_id)
        if not src:
            errors.append(
                f"StatusFlowItem {statusflow_id}/{status_id} has no matching moqui.basic.StatusItem."
            )
            continue
        items.append(
            StatusItemDef(
                status_id=status_id,
                description=src.get("description", status_id),
                sequence_num=int(src.get("sequenceNum", "0")),
                enum_name=normalize_enum_name(status_id, src.get("description", status_id)),
                is_initial=is_initial,
            )
        )

    if not flow_item_initial:
        errors.append(f"No moqui.basic.StatusFlowItem rows found for statusFlowId {statusflow_id}.")

    item_ids = {item.status_id for item in items}
    enum_names: dict[str, str] = {}
    for item in items:
        prev = enum_names.get(item.enum_name)
        if prev and prev != item.status_id:
            errors.append(
                f"Enum-name collision in StatusFlow {statusflow_id}: statuses {prev} and {item.status_id} both normalize to {item.enum_name}."
            )
        enum_names[item.enum_name] = item.status_id
    initial_count = sum(1 for item in items if item.is_initial)
    if initial_count != 1:
        errors.append(
            f"StatusFlow {statusflow_id} must define exactly one initial state; found {initial_count}."
        )
    for tr in transitions:
        if tr.from_status_id not in item_ids:
            errors.append(
                f"Transition {tr.transition_name or tr.from_status_id + '->' + tr.to_status_id} starts from missing state {tr.from_status_id}."
            )
        if tr.to_status_id not in all_flow_items.get(tr.to_status_flow_id, set()):
            errors.append(
                f"Transition {tr.transition_name or tr.from_status_id + '->' + tr.to_status_id} points to missing state "
                f"{tr.to_status_flow_id}/{tr.to_status_id}."
            )
    if errors:
        fail_validation(errors)

    items.sort(key=lambda item: (item.sequence_num, item.status_id))
    transitions.sort(key=lambda t: (t.from_status_id, t.transition_sequence, t.to_status_id))
    return items, transitions


def load_template(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def render_main_status(items: list[StatusItemDef]) -> str:
    lines = []
    for idx, item in enumerate(items):
        if len(items) == 1:
            lines.append(f"    {item.enum_name} := 0")
        elif idx == 0:
            lines.append(f"    {item.enum_name} := 0,")
        elif idx == len(items) - 1:
            lines.append(f"    {item.enum_name}")
        else:
            lines.append(f"    {item.enum_name},")
    return "\n".join(lines)


def render_main_fsm_blocks(
    statusflow_id: str,
    items: list[StatusItemDef],
    transitions: list[TransitionDef],
    request_map: dict[str, str],
    fsm: dict | None = None,
    upstream_model: dict | None = None,
) -> str:
    enum_name_by_status_id = {item.status_id: item.enum_name for item in items}
    item_by_status_id = {item.status_id: item for item in items}
    by_from: dict[str, list[TransitionDef]] = {}
    for tr in transitions:
        by_from.setdefault(tr.from_status_id, []).append(tr)

    blocks: list[str] = []
    survey_states = {state["status_id"]: state for state in fsm["states"]} if fsm else {}
    for item in items:
        status_transitions = by_from.get(item.status_id, [])
        lines = [f"    MainStatus.{item.enum_name} :"]
        lines.append(f"        logger(message := '{item.enum_name}.', level := LogLevel.DEBUG);")
        lines.append("")
        lines.append("        (* FSM output function *)")
        if fsm and upstream_model:
            lines.append(f"        {render_output_assignments(survey_states[item.status_id], upstream_model)}")
        else:
            lines.append(f"        __OUTPUT_ASSIGNMENTS_{item.enum_name.upper()}__")
        lines.append("")
        lines.append("        (* FSM status update function *)")
        if status_transitions:
            first = True
            for tr in status_transitions:
                next_name = enum_name_by_status_id.get(tr.to_status_id, normalize_enum_name(tr.to_status_id, tr.to_status_id))
                keyword = "IF" if first else "ELSIF"
                survey_transition = next(
                    (
                        row for row in fsm["transitions"]
                        if row["from_status_id"] == tr.from_status_id and row["to_status_id"] == tr.to_status_id
                    ),
                    None,
                ) if fsm else None
                if tr.to_status_flow_id == statusflow_id:
                    target_request = request_field_name(item_by_status_id[tr.to_status_id], request_map)
                    lines.append(f"        {keyword} dev.{target_request} THEN")
                else:
                    if not survey_transition or not survey_transition["consume_condition"]:
                        raise SystemExit(
                            f"Cross-flow transition {tr.from_status_id} -> {tr.to_status_flow_id}/{tr.to_status_id} "
                            "requires reviewed consume_condition."
                        )
                    lines.append(f"        {keyword} {survey_transition['consume_condition']} THEN")
                lines.append(f"            (* {tr.transition_name} -> {next_name} *)")
                if tr.to_status_flow_id == statusflow_id:
                    lines.append(f"            dev.status := MainStatus.{next_name};")
                else:
                    if not survey_transition or not survey_transition["apply_assignments"]:
                        raise SystemExit(
                            f"Cross-flow transition {tr.from_status_id} -> {tr.to_status_flow_id}/{tr.to_status_id} "
                            "requires reviewed apply_assignments."
                        )
                    lines.extend(f"            {st_assignment(row)}" for row in survey_transition["apply_assignments"])
                first = False
            lines.append("        END_IF;")
        else:
            lines.append("        (* No outgoing transitions declared in StatusFlow *)")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def request_field_name(item: StatusItemDef, request_map: dict[str, str]) -> str:
    mapped = request_map.get(item.enum_name) or request_map.get(item.status_id)
    if mapped:
        return mapped
    return item.enum_name[:1].lower() + item.enum_name[1:] + "Request"


def choose_fault_state(items: list[StatusItemDef], explicit_fault_state: str | None) -> str | None:
    if not items:
        raise SystemExit("Cannot choose a fault state from an empty StatusFlow.")
    if explicit_fault_state:
        return explicit_fault_state
    preferred = ("Fault", "ErrorStop", "EmergencyStop")
    for candidate in preferred:
        for item in items:
            if item.enum_name == candidate:
                return candidate
    return None


def choose_hold_request(items: list[StatusItemDef], request_map: dict[str, str]) -> str:
    if not items:
        raise SystemExit("Cannot choose a hold request from an empty StatusFlow.")
    preferred = ("Standby", "Standstill")
    for candidate in preferred:
        for item in items:
            if item.enum_name == candidate:
                return request_field_name(item, request_map)
    initial_item = next((item for item in items if item.is_initial), items[0])
    return request_field_name(initial_item, request_map)


def choose_break_state(items: list[StatusItemDef], explicit_break_state: str | None) -> str:
    if not items:
        raise SystemExit("Cannot choose a break state from an empty StatusFlow.")
    if explicit_break_state:
        return explicit_break_state
    preferred = ("Standby", "Standstill")
    for candidate in preferred:
        for item in items:
            if item.enum_name == candidate:
                return candidate
    initial_item = next((item for item in items if item.is_initial), items[0])
    return initial_item.enum_name


def render_state_request_declarations(items: list[StatusItemDef], request_map: dict[str, str]) -> str:
    names: list[str] = []
    for item in items:
        field_name = request_field_name(item, request_map)
        if field_name not in names:
            names.append(field_name)
    for extra in ("faultRequest", "faultAck"):
        if extra not in names:
            names.append(extra)
    return "\n".join(f"    {name} : BOOL;" for name in names)


def render_predicate_declarations(fsm: dict | None) -> str:
    if not fsm or not fsm["predicates"]:
        return "    (* No computed predicates declared for this FSM. *)"
    return "\n".join(
        f"    {predicate['name']} : BOOL;" + (f" (* {predicate['comment']} *)" if predicate["comment"] else "")
        for predicate in fsm["predicates"]
    )


def render_predicate_assignments(fsm: dict | None) -> str:
    if not fsm or not fsm["predicates"]:
        return "(* No computed predicates declared for this FSM. *)"
    return "\n".join(
        f"dev.{predicate['name']} := {predicate['expression']};"
        + (f" (* {predicate['comment']} *)" if predicate["comment"] else "")
        for predicate in fsm["predicates"]
    )


def render_request_reset_block(items: list[StatusItemDef], request_map: dict[str, str], hold_request: str) -> str:
    lines = ["dev.faultRequest := FALSE;"]
    seen = {"faultRequest"}
    for item in items:
        request_name = request_field_name(item, request_map)
        if request_name in seen:
            continue
        lines.append(f"dev.{request_name} := FALSE;")
        seen.add(request_name)
    return "\n".join(lines)


def render_state_transition_cases(
    statusflow_id: str,
    items: list[StatusItemDef],
    transitions: list[TransitionDef],
    hold_request: str,
    request_map: dict[str, str],
    fsm: dict | None = None,
) -> str:
    enum_name_by_status_id = {item.status_id: item.enum_name for item in items}
    item_by_status_id = {item.status_id: item for item in items}
    by_from: dict[str, list[TransitionDef]] = {}
    for tr in transitions:
        by_from.setdefault(tr.from_status_id, []).append(tr)

    blocks: list[str] = []
    survey_by_transition = {
        (row["from_status_id"], row["to_status_id"]): row for row in fsm["transitions"]
    } if fsm else {}
    for item in items:
        status_transitions = by_from.get(item.status_id, [])
        lines = [f"    MainStatus.{item.enum_name} :"]
        lines.append(f"        (* State {item.enum_name} transition conditions *)")
        if status_transitions:
            first = True
            for tr in status_transitions:
                next_name = enum_name_by_status_id.get(tr.to_status_id, normalize_enum_name(tr.to_status_id, tr.to_status_id))
                keyword = "IF" if first else "ELSIF"
                survey_transition = survey_by_transition.get((tr.from_status_id, tr.to_status_id))
                condition = survey_transition["condition"] if survey_transition else f"__COND_{item.enum_name.upper()}_TO_{next_name.upper()}__"
                lines.append(f"        {keyword} {condition} THEN")
                lines.append(f"            (* {tr.transition_name} -> {next_name} *)")
                if tr.to_status_flow_id == statusflow_id:
                    target_request = request_field_name(item_by_status_id[tr.to_status_id], request_map)
                    assignments = survey_transition["request_assignments"] if survey_transition else []
                    if assignments:
                        lines.extend(f"            {st_assignment(row)}" for row in assignments)
                    else:
                        lines.append(f"            dev.{target_request} := TRUE;")
                else:
                    if not survey_transition or not survey_transition["request_assignments"]:
                        raise SystemExit(
                            f"Cross-flow transition {tr.from_status_id} -> {tr.to_status_flow_id}/{tr.to_status_id} "
                            "requires reviewed request_assignments."
                        )
                    lines.extend(f"            {st_assignment(row)}" for row in survey_transition["request_assignments"])
                first = False
            lines.append("        END_IF;")
        else:
            lines.append("        ; (* no outgoing transitions declared *)")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def write_rendered(template_text: str, replacements: dict[str, str], output_path: Path) -> None:
    rendered = template_text
    for key, value in replacements.items():
        rendered = rendered.replace(key, value)
    output_path.write_text(rendered, encoding="utf-8")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_session(session_dir: Path) -> tuple[Path, dict]:
    session_path = session_dir / "session.json"
    if not session_path.is_file():
        raise SystemExit(f"session.json not found in session directory: {session_dir}")
    return session_path, json.loads(session_path.read_text(encoding="utf-8"))


def resolve_output_root(args: argparse.Namespace) -> Path:
    if args.output_root_override:
        return args.output_root_override
    if args.session_dir:
        session_path, session = load_session(args.session_dir)
        generated_dir_name = session.get("paths", {}).get("generatedPlcDir", "generated-plc")
        return session_path.parent / generated_dir_name
    return args.output_root


def update_session_metadata(session_dir: Path, component_root: Path) -> None:
    session_path, session = load_session(session_dir)
    rel_component = str(component_root.relative_to(session_dir))
    artifacts = session.setdefault("artifacts", {})
    generated = artifacts.setdefault("generatedPlc", [])
    if rel_component not in generated:
        generated.append(rel_component)
    session["updatedAt"] = utc_now()
    session["currentStage"] = "plc_design"
    session["currentSkill"] = "moqui-plc-designer"
    session["status"] = "needs_review"
    steps = session.setdefault("steps", {})
    step = steps.setdefault("plc_design", {"status": "pending", "notes": ""})
    step["status"] = "generated"
    step["notes"] = f"Generated PLC skeletons for component {component_root.name}; review placeholders and transition semantics before implementation."
    session_path.write_text(json.dumps(session, indent=2) + "\n", encoding="utf-8")


def output_paths(output_root: Path, namespace: str, component_name: str) -> dict[str, Path]:
    component_root = output_root / component_name
    component_dir = component_root / "src" / "main" / namespace / component_name
    device_dir = component_root / "src" / "main" / "org" / "moqui" / "device"
    data_dir = component_root / "data"
    return {
        "component_root": component_root,
        "component_dir": component_dir,
        "device_dir": device_dir,
        "data_dir": data_dir,
        "MainStatus.dut": component_dir / "MainStatus.dut",
        "Main.pou": component_dir / "Main.pou",
        "MainRuleEngine.pou": component_dir / "MainRuleEngine.pou",
        "IOFacade.dut": device_dir / "IOFacade.dut",
        "DeviceFacade.dut": device_dir / "DeviceFacade.dut",
        "DeviceManager.pou": device_dir / "DeviceManager.pou",
        "DeviceDiagnostics.pou": device_dir / "DeviceDiagnostics.pou",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Render MainStatus/Main/MainRuleEngine skeletons from a Moqui StatusFlow")
    parser.add_argument("xml", type=Path, help="Path to DeviceData.xml or another seed XML")
    parser.add_argument("statusflow_id", help="StatusFlow ID to render")
    parser.add_argument(
        "output_root",
        type=Path,
        nargs="?",
        default=Path(__file__).resolve().parent.parent / "output",
        help="Root output directory. The script creates output/<component>/src/main/... under this root.",
    )
    parser.add_argument(
        "--templates-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "references" / "plc-codegen-templates",
        help="Directory containing *.template.* files",
    )
    parser.add_argument(
        "--component-name",
        help="Component/machine name used for the output directory and PLC component path",
    )
    parser.add_argument(
        "--namespace",
        default="mantle",
        help="Top-level PLC namespace folder under src/main, for example mantle",
    )
    parser.add_argument(
        "--request-map",
        type=Path,
        help="Optional JSON file overriding the default StatusName -> statusNameRequest convention",
    )
    parser.add_argument(
        "--fault-state",
        help="Optional explicit fault state enum name. Defaults to Fault/ErrorStop/EmergencyStop if present.",
    )
    parser.add_argument(
        "--break-state",
        help="Optional explicit break/hold state enum name. Defaults to Standby, then Standstill, then the initial state.",
    )
    parser.add_argument(
        "--session-dir",
        type=Path,
        help="Saved session directory; if provided, default output goes to generated-plc/ and session.json is updated",
    )
    parser.add_argument("--output-root-override", type=Path, help="Explicit output root while retaining session survey validation")
    args = parser.parse_args()
    upstream_model = None
    fsm = None
    if args.session_dir:
        validate_upstream_surveys(args.session_dir.resolve())
        upstream_model, fsm = select_fsm_model(args.session_dir.resolve(), args.statusflow_id)

    items, transitions = parse_statusflow(args.xml, args.statusflow_id)
    if not items:
        raise SystemExit(f"No StatusFlowItems found for {args.statusflow_id}")

    initial_state = next((item.enum_name for item in items if item.is_initial), items[0].enum_name)
    component_name = args.component_name or normalize_component_name(args.statusflow_id)
    request_map = load_request_map(args.request_map)
    explicit_fault_state = args.fault_state
    if not explicit_fault_state and fsm and fsm["fault_status_id"]:
        explicit_fault_state = next(
            item.enum_name for item in items if item.status_id == fsm["fault_status_id"]
        )
    fault_state = choose_fault_state(items, explicit_fault_state)
    break_state = choose_break_state(items, args.break_state)
    hold_request = choose_hold_request(items, request_map)
    output_root = resolve_output_root(args)
    paths = output_paths(output_root, args.namespace, component_name)
    for key in ("component_dir", "device_dir", "data_dir"):
        paths[key].mkdir(parents=True, exist_ok=True)

    replacements = {
        "${MAIN_STATUS_ITEMS}": render_main_status(items),
        "${MAIN_STATUS_ENUM}": "MainStatus",
        "${INITIAL_STATUS}": f"MainStatus.{initial_state}",
        "${FAULT_STATUS}": f"MainStatus.{fault_state}" if fault_state else "",
        "${FAULT_OVERRIDE}": (
            f"IF dev.faultRequest THEN dev.status := MainStatus.{fault_state}; END_IF;"
            if fault_state else "(* No fault state defined for this FSM. *)"
        ),
        "${BREAK_STATUS}": f"MainStatus.{break_state}",
        "${COMPONENT_NAME}": component_name,
        "${REQUEST_RESET_BLOCK}": render_request_reset_block(items, request_map, hold_request),
        "${STATE_REQUEST_DECLARATIONS}": render_state_request_declarations(items, request_map),
        "${STATE_TRANSITION_CASES}": render_state_transition_cases(
            args.statusflow_id, items, transitions, hold_request, request_map, fsm
        ),
        "${MAIN_FSM_CASE_BLOCKS}": render_main_fsm_blocks(
            args.statusflow_id, items, transitions, request_map, fsm, upstream_model
        ),
        "${PHYSICAL_INPUT_DECLARATIONS}": "    (* TODO: declare physical input signals from DeviceRequestItem or naming convention *)",
        "${PHYSICAL_OUTPUT_DECLARATIONS}": "    (* TODO: declare physical output signals from DeviceRequestItem or naming convention *)",
        "${ANALOG_SIGNAL_DECLARATIONS}": "    (* TODO: declare REAL process/environment parameters *)",
        "${DIGITAL_SIGNAL_DECLARATIONS}": "    (* TODO: declare BOOL process/environment parameters *)",
        "${PREDICATE_DECLARATIONS}": render_predicate_declarations(fsm),
        "${PROCESS_MODE_DECLARATIONS}": "    (* TODO: declare project-specific process state; keep numerical logic behind BOOL predicates *)",
        "${ATOMIC_DEVICE_DECLARATIONS}": "    (* TODO: declare Actuator/ActuatorGroup/Axis/AxisGroup/ProcessPid instances *)",
        "${DEVICE_MANAGER_CALLS}": "(* TODO: invoke each atomic device instance in deterministic order *)",
        "${BLOCKING_DEVICE_SIGNAL_RULES}": "(* TODO: add blocking device diagnostics rules *)",
        "${SAFETY_SIGNAL_RULES}": "(* TODO: add environmental and safety stop rules *)",
        "${SENSOR_PREDICATES}": render_predicate_assignments(fsm),
        "${INIT_ASSIGNMENTS}": "    ; (* no additional project-specific initialization *)",
        "${FAULT_CONDITION}": (
            fsm.get("global_overrides", {}).get("fault_condition")
            if fsm and isinstance(fsm.get("global_overrides"), dict)
            else ""
        ) or "error OR ((dev.signalMgmt.cumulativeOutputAction AND SignalOutputAction.ImmediateStop) <> 0)",
        "${DONE_ASSIGNMENT}": f"done := {fsm['completion_condition']};" if fsm and fsm["completion_condition"] else "done := FALSE;",
        "${SUBSYSTEM_CONTROLLER_DECLARATIONS}": "    (* No subsystem controllers generated by this single-FSM command. *)",
        "${SUBSYSTEM_CONTROLLER_INIT_CALLS}": "    (* No subsystem controller initialization. *)",
        "${SUBSYSTEM_CONTROLLER_CALLS}": "(* No subsystem controller calls. *)",
        "${SUBSYSTEM_FSM_DECLARATIONS}": "    (* No subsystem FSM state fields generated by this single-FSM command. *)",
    }

    files = [
        ("MainStatus.template.dut", paths["MainStatus.dut"]),
        ("Main.template.pou", paths["Main.pou"]),
        ("MainRuleEngine.template.pou", paths["MainRuleEngine.pou"]),
        ("IOFacade.template.dut", paths["IOFacade.dut"]),
        ("DeviceFacade.template.dut", paths["DeviceFacade.dut"]),
        ("DeviceManager.template.pou", paths["DeviceManager.pou"]),
        ("DeviceDiagnostics.template.pou", paths["DeviceDiagnostics.pou"]),
    ]
    for template_name, out_path in files:
        write_rendered(
            load_template(args.templates_dir / template_name),
            replacements,
            out_path,
        )

    if args.session_dir:
        update_session_metadata(args.session_dir.resolve(), paths["component_root"].resolve())
    print(f"Rendered {args.statusflow_id} into {paths['component_root']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

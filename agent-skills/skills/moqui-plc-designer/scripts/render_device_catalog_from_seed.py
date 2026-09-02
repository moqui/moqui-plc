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
Render IOFacade, DeviceFacade, DeviceManager, and DeviceDiagnostics
from Moqui seed XML data.

Primary sources:
  - Device / PhysicalDevice
  - ParameterDef / Parameter
  - DeviceRequest / DeviceRequestItem

This script fills the stable catalog/orchestration layer for supported atomic
moqui-plc FB types.
Fieldbus-specific mapping in InputSignalUpdate/OutputSignalUpdate remains manual.
Main/MainRuleEngine behavior remains outside this script.
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

from survey_validation import validate_upstream_surveys


@dataclass
class DeviceDef:
    device_id: str
    parent_device_id: str | None
    device_type_enum_id: str | None
    control_method_enum_id: str | None
    statusflow_id: str | None
    status_id: str | None


@dataclass
class PhysicalDeviceRec:
    device_id: str
    device_name: str | None


@dataclass
class ParameterDefRec:
    parameter_def_id: str
    parameter_name: str
    parameter_type_enum_id: str
    purpose_enum_id: str | None
    description: str | None


@dataclass
class ParameterRec:
    parameter_id: str
    device_id: str
    parameter_def_id: str
    parameter_alias: str | None
    sequence_num: int


@dataclass
class DeviceRequestRec:
    request_name: str
    device_id: str
    request_type_enum_id: str | None


@dataclass
class DeviceRequestItemRec:
    request_name: str
    parameter_id: str | None
    request_item_name: str | None
    sequence_num: int
    item_type_enum_id: str | None
    query: str | None


@dataclass
class StatusItemDef:
    status_id: str
    description: str
    sequence_num: int
    enum_name: str
    is_initial: bool


TAG_DEVICE = "moqui.device.Device"
TAG_PARAMETER_DEF = "moqui.math.ParameterDef"
TAG_PARAMETER = "moqui.math.Parameter"
TAG_DEVICE_REQUEST = "moqui.device.DeviceRequest"
TAG_DEVICE_REQUEST_ITEM = "moqui.device.DeviceRequestItem"
TAG_PHYSICAL_DEVICE = "moqui.device.PhysicalDevice"
TAG_STATUS_ITEM = "moqui.basic.StatusItem"
TAG_STATUS_FLOW_ITEM = "moqui.basic.StatusFlowItem"


def fail_validation(errors: list[str]) -> None:
    raise SystemExit("Seed validation failed:\n- " + "\n- ".join(errors))


def local_name(tag: str) -> str:
    return tag.split("}", 1)[-1]


def normalize_component_name(name: str) -> str:
    return name[:1].lower() + name[1:] if name else "component"


def normalize_enum_name(status_id: str, description: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "", description)
    if cleaned:
        return cleaned
    fallback = re.sub(r"^[A-Z][a-z]?[a-z]?", "", status_id)
    return fallback or status_id


def to_lower_camel(raw: str) -> str:
    if not raw:
        return "value"
    chunks = re.findall(r"[A-Za-z0-9]+", raw)
    parts = [
        word
        for chunk in chunks
        for word in re.findall(r"[A-Z]+(?=[A-Z][a-z]|\d|$)|[A-Z]?[a-z]+|\d+", chunk)
    ]
    if not parts:
        return "value"
    head = parts[0].lower()
    tail = "".join(part[:1].upper() + part[1:] for part in parts[1:])
    return head + tail


def to_upper_camel(raw: str) -> str:
    lower = to_lower_camel(raw)
    return lower[:1].upper() + lower[1:] if lower else "Value"


def load_request_map(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("Request map must be a JSON object")
    return {str(k): str(v) for k, v in data.items()}


def load_template(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_rendered(template_text: str, replacements: dict[str, str], output_path: Path) -> None:
    rendered = template_text
    for key, value in replacements.items():
        rendered = rendered.replace(key, value)
    output_path.parent.mkdir(parents=True, exist_ok=True)
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
    step["notes"] = f"Generated device catalogs for component {component_root.name}; cross-check generated PLC declarations against seed data before downstream use."
    session_path.write_text(json.dumps(session, indent=2) + "\n", encoding="utf-8")


def output_paths(output_root: Path, namespace: str, component_name: str) -> dict[str, Path]:
    component_root = output_root / component_name
    component_dir = component_root / "src" / "main" / namespace / component_name
    device_dir = component_root / "src" / "main" / "org" / "moqui" / "device"
    return {
        "component_root": component_root,
        "component_dir": component_dir,
        "device_dir": device_dir,
        "DeviceFacade.dut": device_dir / "DeviceFacade.dut",
        "IOFacade.dut": device_dir / "IOFacade.dut",
        "DeviceManager.pou": device_dir / "DeviceManager.pou",
        "DeviceDiagnostics.pou": device_dir / "DeviceDiagnostics.pou",
    }


def parse_seed_files(xml_paths: list[Path]) -> tuple[
    dict[str, DeviceDef],
    dict[str, PhysicalDeviceRec],
    dict[str, ParameterDefRec],
    dict[str, ParameterRec],
    dict[str, DeviceRequestRec],
    list[DeviceRequestItemRec],
    dict[str, dict[str, str]],
    dict[str, bool],
]:
    devices: dict[str, DeviceDef] = {}
    physical_devices: dict[str, PhysicalDeviceRec] = {}
    parameter_defs: dict[str, ParameterDefRec] = {}
    parameters: dict[str, ParameterRec] = {}
    device_requests: dict[str, DeviceRequestRec] = {}
    request_items: list[DeviceRequestItemRec] = []
    status_items: dict[str, dict[str, str]] = {}
    flow_item_initial: dict[str, bool] = {}

    for xml_path in xml_paths:
        root = ET.parse(xml_path).getroot()
        for elem in root.iter():
            tag = local_name(elem.tag)
            if tag == TAG_DEVICE:
                device_id = elem.attrib["deviceId"]
                devices[device_id] = DeviceDef(
                    device_id=device_id,
                    parent_device_id=elem.attrib.get("parentDeviceId"),
                    device_type_enum_id=elem.attrib.get("deviceTypeEnumId"),
                    control_method_enum_id=elem.attrib.get("controlMethodEnumId"),
                    statusflow_id=elem.attrib.get("statusFlowId"),
                    status_id=elem.attrib.get("statusId"),
                )
            elif tag == TAG_PHYSICAL_DEVICE:
                device_id = elem.attrib["deviceId"]
                physical_devices[device_id] = PhysicalDeviceRec(
                    device_id=device_id,
                    device_name=elem.attrib.get("deviceName"),
                )
            elif tag == TAG_PARAMETER_DEF:
                parameter_def_id = elem.attrib["parameterDefId"]
                parameter_defs[parameter_def_id] = ParameterDefRec(
                    parameter_def_id=parameter_def_id,
                    parameter_name=elem.attrib.get("parameterName", parameter_def_id),
                    parameter_type_enum_id=elem.attrib.get("parameterTypeEnumId", "PtNumberDecimal"),
                    purpose_enum_id=elem.attrib.get("purposeEnumId"),
                    description=elem.attrib.get("description"),
                )
            elif tag == TAG_PARAMETER:
                # Configuration-scoped values are recipes, not DeviceFacade fields.
                if not elem.attrib.get("deviceId"):
                    continue
                parameter_id = elem.attrib["parameterId"]
                parameters[parameter_id] = ParameterRec(
                    parameter_id=parameter_id,
                    device_id=elem.attrib["deviceId"],
                    parameter_def_id=elem.attrib["parameterDefId"],
                    parameter_alias=elem.attrib.get("parameterAlias"),
                    sequence_num=int(elem.attrib.get("sequenceNum", "0")),
                )
            elif tag == TAG_DEVICE_REQUEST:
                request_name = elem.attrib["requestName"]
                device_requests[request_name] = DeviceRequestRec(
                    request_name=request_name,
                    device_id=elem.attrib["deviceId"],
                    request_type_enum_id=elem.attrib.get("requestTypeEnumId"),
                )
            elif tag == TAG_DEVICE_REQUEST_ITEM:
                request_name = elem.attrib.get("requestName") or elem.attrib.get("deviceRequestId")
                if not request_name:
                    continue
                request_items.append(
                    DeviceRequestItemRec(
                        request_name=request_name,
                        parameter_id=elem.attrib.get("parameterId"),
                        request_item_name=elem.attrib.get("requestItemName"),
                        sequence_num=int(elem.attrib.get("sequenceNum", "0")),
                        item_type_enum_id=elem.attrib.get("itemTypeEnumId"),
                        query=elem.attrib.get("query"),
                    )
                )
            elif tag == TAG_STATUS_ITEM:
                status_items[elem.attrib["statusId"]] = elem.attrib
            elif tag == TAG_STATUS_FLOW_ITEM:
                flow_key = f"{elem.attrib.get('statusFlowId')}::{elem.attrib.get('statusId')}"
                flow_item_initial[flow_key] = elem.attrib.get("isInitial") == "Y"

    return devices, physical_devices, parameter_defs, parameters, device_requests, request_items, status_items, flow_item_initial


def parse_statusflow_items(
    statusflow_id: str | None,
    status_items: dict[str, dict[str, str]],
    flow_item_initial: dict[str, bool],
) -> list[StatusItemDef]:
    if not statusflow_id:
        return []
    items: list[StatusItemDef] = []
    for flow_key, is_initial in flow_item_initial.items():
        flow_id, status_id = flow_key.split("::", 1)
        if flow_id != statusflow_id:
            continue
        src = status_items.get(status_id)
        if not src:
            continue
        description = src.get("description", status_id)
        items.append(
            StatusItemDef(
                status_id=status_id,
                description=description,
                sequence_num=int(src.get("sequenceNum", "0")),
                enum_name=normalize_enum_name(status_id, description),
                is_initial=is_initial,
            )
        )
    items.sort(key=lambda item: (item.sequence_num, item.status_id))
    return items


def request_direction(request_type_enum_id: str | None) -> str | None:
    if not request_type_enum_id:
        return None
    if request_type_enum_id in {"DrtWrite"}:
        return "output"
    if request_type_enum_id in {"DrtRead", "DrtCyclic", "DrtSubscribe"}:
        return "input"
    if request_type_enum_id in {"DrtUnsubscribe", "DrtExec", "DrtExport", "DrtTransfer"}:
        return None
    return None


def validate_seed_graph(
    root_device_id: str,
    devices: dict[str, DeviceDef],
    physical_devices: dict[str, PhysicalDeviceRec],
    parameter_defs: dict[str, ParameterDefRec],
    parameters: dict[str, ParameterRec],
    device_requests: dict[str, DeviceRequestRec],
    request_items: list[DeviceRequestItemRec],
    status_items: dict[str, dict[str, str]],
    flow_item_initial: dict[str, bool],
    require_physical_root: bool = True,
) -> None:
    errors: list[str] = []
    if root_device_id not in devices:
        errors.append(f"Root Device {root_device_id} not found.")
        fail_validation(errors)
    if require_physical_root and root_device_id not in physical_devices:
        errors.append(f"Root Device {root_device_id} has no matching PhysicalDevice row.")

    root_device = devices[root_device_id]
    if root_device.statusflow_id:
        statusflow_items = parse_statusflow_items(root_device.statusflow_id, status_items, flow_item_initial)
        if not statusflow_items:
            errors.append(
                f"Root Device {root_device_id} references statusFlowId {root_device.statusflow_id}, but no matching StatusFlowItem rows were found."
            )
        initial_count = sum(1 for item in statusflow_items if item.is_initial)
        if statusflow_items and initial_count != 1:
            errors.append(
                f"StatusFlow {root_device.statusflow_id} must define exactly one initial state; found {initial_count}."
            )

    for parameter in parameters.values():
        if parameter.device_id not in devices:
            errors.append(
                f"Parameter {parameter.parameter_id} references unknown deviceId {parameter.device_id}."
            )
        if parameter.parameter_def_id not in parameter_defs:
            errors.append(
                f"Parameter {parameter.parameter_id} references unknown parameterDefId {parameter.parameter_def_id}."
            )

    for request in device_requests.values():
        if request.device_id not in devices:
            errors.append(
                f"DeviceRequest {request.request_name} references unknown deviceId {request.device_id}."
            )

    for item in request_items:
        if item.request_name not in device_requests:
            errors.append(
                f"DeviceRequestItem {item.request_item_name or item.parameter_id or '?'} references unknown request {item.request_name}."
            )
        if item.parameter_id and item.parameter_id not in parameters:
            errors.append(
                f"DeviceRequestItem {item.request_item_name or item.request_name} references unknown parameterId {item.parameter_id}."
            )

    if errors:
        fail_validation(errors)


def purpose_comment(purpose_enum_id: str | None) -> str:
    if purpose_enum_id == "PpFeedback":
        return "feedback"
    if purpose_enum_id == "PpDeviceConfiguration":
        return "recipe/config"
    if purpose_enum_id == "PpControl":
        return "control"
    if purpose_enum_id == "PpStatus":
        return "status"
    if purpose_enum_id == "PpCondition":
        return "condition"
    if purpose_enum_id == "PpEvent":
        return "event"
    if purpose_enum_id == "PpSample":
        return "sample"
    return "logical parameter"


def parameter_type_to_iec(parameter_type_enum_id: str) -> str:
    if parameter_type_enum_id in {"PtNumberDecimal", "PtNumberFloat", "PtCurrencyAmount", "PtCurrencyPrecise"}:
        return "REAL"
    if parameter_type_enum_id in {"PtNumberInteger"}:
        return "DINT"
    if parameter_type_enum_id in {"PtBitSet"}:
        return "WORD"
    if parameter_type_enum_id in {"PtByte"}:
        return "BYTE"
    if parameter_type_enum_id in {"PtTextIndicator"}:
        return "BOOL"
    if parameter_type_enum_id in {"PtTextShort", "PtText"}:
        return "STRING"
    if parameter_type_enum_id in {"PtTime"}:
        return "TIME"
    return "REAL"


def request_item_type_to_iec(item_type_enum_id: str | None) -> str:
    mapping = {
        "DritBool": "BOOL",
        "DritByte": "BYTE",
        "DritWord": "WORD",
        "DritDWord": "DWORD",
        "DritLWord": "LWORD",
        "DritInt": "INT",
        "DritUInt": "UINT",
        "DritDInt": "DINT",
        "DritUDInt": "UDINT",
        "DritReal": "REAL",
        "DritLReal": "LREAL",
    }
    return mapping.get(item_type_enum_id or "", "WORD")


def request_field_name(item: StatusItemDef, request_map: dict[str, str]) -> str:
    mapped = request_map.get(item.enum_name) or request_map.get(item.status_id)
    if mapped:
        return mapped
    return item.enum_name[:1].lower() + item.enum_name[1:] + "Request"


def render_state_request_declarations(items: list[StatusItemDef], request_map: dict[str, str]) -> str:
    names: list[str] = []
    for item in items:
        field_name = request_field_name(item, request_map)
        if field_name not in names:
            names.append(field_name)
    # Must match render_statusflow_templates.py's reserved extras exactly:
    # render_codesys_applications.py assembles DeviceFacade.dut from this
    # function (via a subprocess call to this script) but assembles
    # MainRuleEngine.pou/Main.pou from render_statusflow_templates.py's
    # logic. The two lists previously diverged ("resetRequest" here vs.
    # "faultAck" there), so any FSM survey using a manual fault-acknowledge
    # transition (dev.faultAck) would generate a MainRuleEngine.pou that
    # assigns a field DeviceFacade.dut never declares.
    for extra in ("faultRequest", "faultAck"):
        if extra not in names:
            names.append(extra)
    return "\n".join(f"    {name} : BOOL;" for name in names)


def render_parameter_declarations(
    root_device_id: str,
    subtree_device_ids: set[str],
    devices: dict[str, DeviceDef],
    physical_devices: dict[str, PhysicalDeviceRec],
    parameters: dict[str, ParameterRec],
    parameter_defs: dict[str, ParameterDefRec],
    exclude_field_names: frozenset[str] = frozenset(),
) -> tuple[str, str]:
    analog_lines: list[str] = []
    digital_lines: list[str] = []
    collisions: dict[str, list[str]] = {}
    rows = [row for row in parameters.values() if row.device_id in subtree_device_ids]
    rows.sort(key=lambda row: (row.sequence_num, row.parameter_id))
    seen: set[str] = set()
    for row in rows:
        pdef = parameter_defs.get(row.parameter_def_id)
        if not pdef:
            continue
        base_name = row.parameter_alias or pdef.parameter_name or pdef.parameter_def_id
        if row.device_id == root_device_id:
            field_name = to_lower_camel(base_name)
        else:
            physical = physical_devices.get(row.device_id)
            device_name = physical.device_name if physical and physical.device_name else row.device_id
            field_name = to_lower_camel(device_name) + to_upper_camel(base_name)
        if field_name in exclude_field_names:
            # Already declared (with its correct native IEC type and default
            # value) by render_atomic_device_blocks() for this same FB
            # instance. Declaring it again here would produce a duplicate
            # STRUCT member -- invalid IEC 61131-3.
            continue
        if field_name in seen:
            collisions.setdefault(field_name, []).append(row.parameter_id)
            continue
        seen.add(field_name)
        collisions.setdefault(field_name, []).append(row.parameter_id)
        iec_type = parameter_type_to_iec(pdef.parameter_type_enum_id)
        comment = pdef.description or purpose_comment(pdef.purpose_enum_id)
        line = f"    {field_name} : {iec_type};"
        if comment:
            line += f" (* {comment} *)"
        if iec_type == "REAL":
            analog_lines.append(line)
        else:
            digital_lines.append(line)
    if not analog_lines:
        analog_lines.append("    (* No REAL process/environment parameters derived from the selected seed scope. *)")
    if not digital_lines:
        digital_lines.append("    (* No BOOL/WORD/STRING logical parameters derived from the selected seed scope. *)")
    duplicate_fields = {name: ids for name, ids in collisions.items() if len(ids) > 1}
    if duplicate_fields:
        details = [f"{name} <- {', '.join(ids)}" for name, ids in sorted(duplicate_fields.items())]
        fail_validation(["Parameter naming collisions detected after IEC normalization:"] + details)
    return "\n".join(analog_lines), "\n".join(digital_lines)


def infer_signal_name(item: DeviceRequestItemRec, parameter_defs_by_id: dict[str, ParameterDefRec], parameters_by_id: dict[str, ParameterRec]) -> str:
    if item.request_item_name:
        return to_lower_camel(item.request_item_name)
    if item.parameter_id and item.parameter_id in parameters_by_id:
        parameter = parameters_by_id[item.parameter_id]
        pdef = parameter_defs_by_id.get(parameter.parameter_def_id)
        if pdef:
            return to_lower_camel(pdef.parameter_name) + "Signal"
    return "unnamedSignal"


def render_io_declarations(
    subtree_device_ids: set[str],
    request_items: list[DeviceRequestItemRec],
    device_requests: dict[str, DeviceRequestRec],
    parameter_defs: dict[str, ParameterDefRec],
    parameters: dict[str, ParameterRec],
) -> tuple[str, str]:
    inputs: list[str] = []
    outputs: list[str] = []
    collisions: dict[str, list[str]] = {}
    seen_inputs: set[str] = set()
    seen_outputs: set[str] = set()
    for item in sorted(request_items, key=lambda row: (row.request_name, row.sequence_num, row.parameter_id or "")):
        request = device_requests.get(item.request_name)
        if not request or request.device_id not in subtree_device_ids:
            continue
        direction = request_direction(request.request_type_enum_id)
        if direction is None:
            continue
        field_name = infer_signal_name(item, parameter_defs, parameters)
        iec_type = request_item_type_to_iec(item.item_type_enum_id)
        query_comment = f"{request.request_name}"
        if item.query:
            query_comment += f" | {item.query}"
        line = f"    {field_name} : {iec_type}; (* {query_comment} *)"
        collisions.setdefault(field_name, []).append(f"{request.request_name}#{item.sequence_num}")
        if direction == "output":
            if field_name not in seen_outputs:
                outputs.append(line)
                seen_outputs.add(field_name)
        else:
            if field_name not in seen_inputs:
                inputs.append(line)
                seen_inputs.add(field_name)
    if not inputs:
        inputs.append("    (* No physical input declarations derived; device-tree binding remains manual. *)")
    if not outputs:
        outputs.append("    (* No physical output declarations derived; device-tree binding remains manual. *)")
    duplicate_fields = {name: ids for name, ids in collisions.items() if len(ids) > 1}
    if duplicate_fields:
        details = [f"{name} <- {', '.join(ids)}" for name, ids in sorted(duplicate_fields.items())]
        fail_validation(["Physical I/O naming collisions detected after IEC normalization:"] + details)
    return "\n".join(inputs), "\n".join(outputs)


def direct_child_devices(root_device_id: str, devices: dict[str, DeviceDef]) -> list[DeviceDef]:
    children = [device for device in devices.values() if device.parent_device_id == root_device_id]
    children.sort(key=lambda device: device.device_id)
    return children


def subtree_device_ids(root_device_id: str, devices: dict[str, DeviceDef]) -> set[str]:
    result = {root_device_id}
    frontier = [root_device_id]
    while frontier:
        current = frontier.pop()
        for device in devices.values():
            if device.parent_device_id == current and device.device_id not in result:
                result.add(device.device_id)
                frontier.append(device.device_id)
    return result


def logical_device_name(device: DeviceDef, physical_devices: dict[str, PhysicalDeviceRec]) -> str:
    physical = physical_devices.get(device.device_id)
    if physical and physical.device_name:
        return to_lower_camel(physical.device_name)
    return to_lower_camel(device.device_id)


def infer_atomic_kind(device: DeviceDef) -> str | None:
    control = device.control_method_enum_id or ""
    statusflow = device.statusflow_id or ""
    device_type = device.device_type_enum_id or ""
    if device_type == "DtMoquiPlcActuator":
        return "Actuator"
    if device_type == "DtMoquiPlcActuatorGroup":
        return "ActuatorGroup"
    if device_type == "DtMoquiPlcProcessPID":
        return "ProcessPid"
    if device_type == "DtMoquiPlcAxis":
        return "Axis"
    if device_type == "DtMoquiPlcAxisGroup":
        return "AxisGroup"
    if device_type == "DtMoquiPlcSignalMgmt":
        return "SignalMgmt"
    if "AxisGroup" in statusflow or device_type in {"DtDriveGroup"}:
        return "AxisGroup"
    if "Axis" in statusflow or device_type in {"DtDrive", "DtMultiDrives"}:
        return "Axis"
    if control in {
        "DcmPIDControl",
        "DcmPIControl",
        "DcmPDControl",
        "DcmPControl",
        "DcmIPID",
    }:
        return "ProcessPid"
    if control in {
        "DcmDoubleActuationDoubleFeedback",
        "DcmSingleActuationDoubleFeedback",
        "DcmSingleActuationEnableFeedback",
        "DcmSingleActuationDisableFeedback",
        "DcmSingleActuationNoFeedback",
        "DcmDoubleActuationNoRetain",
        "DcmNoActuationSingleFeedback",
    }:
        if device_type.endswith("Group"):
            return "ActuatorGroup"
        return "Actuator"
    return None


def device_parameters(
    device_id: str,
    parameters: dict[str, ParameterRec],
    parameter_defs: dict[str, ParameterDefRec],
) -> list[tuple[ParameterRec, ParameterDefRec]]:
    rows: list[tuple[ParameterRec, ParameterDefRec]] = []
    for parameter in parameters.values():
        if parameter.device_id != device_id:
            continue
        pdef = parameter_defs.get(parameter.parameter_def_id)
        if pdef:
            rows.append((parameter, pdef))
    rows.sort(key=lambda row: (row[0].sequence_num, row[0].parameter_id))
    return rows


def field_name_for_parameter(
    root_device_id: str,
    device_id: str,
    physical_devices: dict[str, PhysicalDeviceRec],
    parameter: ParameterRec,
    parameter_def: ParameterDefRec,
) -> str:
    base_name = parameter.parameter_alias or parameter_def.parameter_name or parameter_def.parameter_def_id
    if device_id == root_device_id:
        return to_lower_camel(base_name)
    physical = physical_devices.get(device_id)
    device_name = physical.device_name if physical and physical.device_name else device_id
    return to_lower_camel(device_name) + to_upper_camel(base_name)


def infer_process_pid_fields(
    root_device_id: str,
    device: DeviceDef,
    physical_devices: dict[str, PhysicalDeviceRec],
    parameters: dict[str, ParameterRec],
    parameter_defs: dict[str, ParameterDefRec],
) -> tuple[str | None, str | None]:
    # Exact-match only. A substring/purpose-based heuristic here previously
    # matched the wrong Parameter whenever any other Parameter on the same
    # device also carried purpose PpFeedback, or had a name that merely
    # *contains* "feedback"/"setpoint" (e.g. a status field named "At
    # Setpoint" contains the substring "setpoint" and would win the match
    # before the real Setpoint field, purely by alphabetical parameter_id
    # tie-break). The atomic component template always names these fields
    # exactly "Feedback" and "Setpoint" (see process-pid-seed-template.xml),
    # so exact equality is both sufficient and deterministic.
    setpoint_field: str | None = None
    feedback_field: str | None = None
    for parameter, pdef in device_parameters(device.device_id, parameters, parameter_defs):
        field_name = field_name_for_parameter(root_device_id, device.device_id, physical_devices, parameter, pdef)
        raw_name = (parameter.parameter_alias or pdef.parameter_name or "").strip().lower().replace(" ", "")
        if feedback_field is None and raw_name == "feedback":
            feedback_field = field_name
        if setpoint_field is None and raw_name in ("setpoint", "reference", "ref"):
            setpoint_field = field_name
    return setpoint_field, feedback_field


def append_unique(lines: list[str], *new_lines: str) -> None:
    for line in new_lines:
        if line not in lines:
            lines.append(line)


def render_actuator_group_block(field_name: str, device_label: str) -> tuple[list[str], str]:
    declarations = [
        f"    {field_name}EnableRequests : ARRAY[1..ACTUATOR_GROUP_MAX_SIZE] OF BOOL;",
        f"    {field_name}DisableRequests : ARRAY[1..ACTUATOR_GROUP_MAX_SIZE] OF BOOL;",
        f"    {field_name}ActuatorGroupId : STRING;",
        f"    {field_name}ActuatorGroupName : STRING;",
        f"    {field_name}ActuatorNum : UINT := 1;",
        f"    {field_name}MinRunning : UINT := 0;",
        f"    {field_name}MaxRunning : UINT := 1;",
        f"    {field_name}DemandSetpoint : REAL;",
        f"    {field_name}StartPoints : ARRAY[0..7] OF REAL;",
        f"    {field_name}StopPoints : ARRAY[0..7] OF REAL;",
        f"    {field_name}StartDelay : TIME := T#10s;",
        f"    {field_name}StopDelay : TIME := T#10s;",
        f"    {field_name}Autochange : ActuatorGroupAutochange := ActuatorGroupAutochange.None;",
        f"    {field_name}AutochangeInterval : TIME := T#1h;",
        f"    {field_name}MaxWearImbalance : REAL := 72.0;",
        f"    {field_name}AutochangeLevel : REAL := 100.0;",
        f"    {field_name}AutochangeTrigger : BOOL;",
        f"    {field_name}ActuatorEnabled : ARRAY[1..ACTUATOR_GROUP_MAX_SIZE] OF BOOL;",
        f"    {field_name}ActuatorFault : ARRAY[1..ACTUATOR_GROUP_MAX_SIZE] OF BOOL;",
        f"    {field_name}ActuatorInterlocked : ARRAY[1..ACTUATOR_GROUP_MAX_SIZE] OF BOOL;",
        f"    {field_name}RunHours : ARRAY[1..ACTUATOR_GROUP_MAX_SIZE] OF REAL;",
        f"    {field_name}GroupEnable : BOOL;",
        f"    {field_name}GroupDisable : BOOL;",
        f"    {field_name} : ActuatorGroup;",
    ]
    call = "\n".join(
        [
            f"(* {device_label} *)",
            f"dev.{field_name}(",
            f"    enableRequests := dev.{field_name}EnableRequests,",
            f"    disableRequests := dev.{field_name}DisableRequests,",
            f"    actuatorGroupId := dev.{field_name}ActuatorGroupId,",
            f"    actuatorGroupName := dev.{field_name}ActuatorGroupName,",
            f"    actuatorNum := dev.{field_name}ActuatorNum,",
            f"    minRunning := dev.{field_name}MinRunning,",
            f"    maxRunning := dev.{field_name}MaxRunning,",
            f"    demandSetpoint := dev.{field_name}DemandSetpoint,",
            f"    startPoints := dev.{field_name}StartPoints,",
            f"    stopPoints := dev.{field_name}StopPoints,",
            f"    startDelay := dev.{field_name}StartDelay,",
            f"    stopDelay := dev.{field_name}StopDelay,",
            f"    autochange := dev.{field_name}Autochange,",
            f"    autochangeInterval := dev.{field_name}AutochangeInterval,",
            f"    maxWearImbalance := dev.{field_name}MaxWearImbalance,",
            f"    autochangeLevel := dev.{field_name}AutochangeLevel,",
            f"    autochangeTrigger := dev.{field_name}AutochangeTrigger,",
            f"    actuatorEnabled := dev.{field_name}ActuatorEnabled,",
            f"    actuatorFault := dev.{field_name}ActuatorFault,",
            f"    actuatorInterlocked := dev.{field_name}ActuatorInterlocked,",
            f"    runHours := dev.{field_name}RunHours,",
            f"    groupEnable := dev.{field_name}GroupEnable,",
            f"    groupDisable := dev.{field_name}GroupDisable);",
        ]
    )
    return declarations, call


def render_axis_block(field_name: str, device_label: str) -> tuple[list[str], str]:
    declarations = [
        f"    {field_name}AxisEnable : BOOL;",
        f"    {field_name}Slave : SM3_Basic.AXIS_REF_SM3;",
        f"    {field_name}Cmd : AxisCmd := AxisCmd.Idle;",
        f"    {field_name}Position : REAL;",
        f"    {field_name}Distance : REAL;",
        f"    {field_name}Velocity : REAL;",
        f"    {field_name}VelocityDiff : REAL;",
        f"    {field_name}Acceleration : REAL;",
        f"    {field_name}Deceleration : REAL;",
        f"    {field_name}Jerk : REAL;",
        f"    {field_name}BufferMode : SM3_Basic.MC_BUFFER_MODE := SM3_Basic.MC_BUFFER_MODE.aborting;",
        f"    {field_name}Direction : SM3_Basic.MC_Direction := SM3_Basic.MC_DIRECTION.positive;",
        f"    {field_name}HomePosition : REAL := 0.0;",
        f"    {field_name}Master : REFERENCE TO SM3_Basic.AXIS_REF_SM3;",
        f"    {field_name}TriggerInput : REFERENCE TO SM3_Basic.TRIGGER_REF;",
        f"    {field_name}PositionProfile : REFERENCE TO SM3_Basic.MC_TP_REF;",
        f"    {field_name}VelocityProfile : REFERENCE TO SM3_Basic.MC_TV_REF;",
        f"    {field_name}AccelerationProfile : REFERENCE TO SM3_Basic.MC_TA_REF;",
        f"    {field_name}RatioNumerator : DINT := 1;",
        f"    {field_name}RatioDenominator : DINT := 1;",
        f"    {field_name}MasterSyncPos : LREAL := 0.0;",
        f"    {field_name}SlaveSyncPos : LREAL := 0.0;",
        f"    {field_name}CamId : SM3_Basic.MC_CAM_ID;",
        f"    {field_name}CamVersion : DWORD := 0;",
        f"    {field_name}StartMode : SM3_Basic.MC_STARTMODE := SM3_Basic.MC_STARTMODE.absolute;",
        f"    {field_name}MasterOffset : LREAL := 0.0;",
        f"    {field_name}SlaveOffset : LREAL := 0.0;",
        f"    {field_name}PhaseShift : LREAL;",
        f"    {field_name}SetPositionMode : BOOL := FALSE;",
        f"    {field_name}OverrideEnable : BOOL;",
        f"    {field_name}VelFactor : REAL := 1.0;",
        f"    {field_name}AccFactor : REAL := 1.0;",
        f"    {field_name}JerkFactor : REAL := 1.0;",
        f"    {field_name}JogForward : BOOL;",
        f"    {field_name}JogBackward : BOOL;",
        f"    {field_name}Reset : BOOL;",
        f"    {field_name}ParameterNumber : WORD;",
        f"    {field_name}ParameterValue : LREAL;",
        f"    {field_name}ParameterBoolValue : BOOL;",
        f"    {field_name}TouchProbeWindow : BOOL;",
        f"    {field_name}TouchProbeFirst : LREAL;",
        f"    {field_name}TouchProbeLast : LREAL;",
        f"    {field_name} : Axis;",
    ]
    call = "\n".join(
        [
            f"(* {device_label} *)",
            f"dev.{field_name}(",
            f"    axisEnable := dev.{field_name}AxisEnable,",
            f"    slave := dev.{field_name}Slave,",
            f"    cmd := dev.{field_name}Cmd,",
            f"    position := dev.{field_name}Position,",
            f"    distance := dev.{field_name}Distance,",
            f"    velocity := dev.{field_name}Velocity,",
            f"    velocityDiff := dev.{field_name}VelocityDiff,",
            f"    acceleration := dev.{field_name}Acceleration,",
            f"    deceleration := dev.{field_name}Deceleration,",
            f"    jerk := dev.{field_name}Jerk,",
            f"    bufferMode := dev.{field_name}BufferMode,",
            f"    direction := dev.{field_name}Direction,",
            f"    homePosition := dev.{field_name}HomePosition,",
            f"    master := dev.{field_name}Master,",
            f"    triggerInput := dev.{field_name}TriggerInput,",
            f"    positionProfile := dev.{field_name}PositionProfile,",
            f"    velocityProfile := dev.{field_name}VelocityProfile,",
            f"    accelerationProfile := dev.{field_name}AccelerationProfile,",
            f"    ratioNumerator := dev.{field_name}RatioNumerator,",
            f"    ratioDenominator := dev.{field_name}RatioDenominator,",
            f"    masterSyncPos := dev.{field_name}MasterSyncPos,",
            f"    slaveSyncPos := dev.{field_name}SlaveSyncPos,",
            f"    camId := dev.{field_name}CamId,",
            f"    camVersion := dev.{field_name}CamVersion,",
            f"    startMode := dev.{field_name}StartMode,",
            f"    masterOffset := dev.{field_name}MasterOffset,",
            f"    slaveOffset := dev.{field_name}SlaveOffset,",
            f"    phaseShift := dev.{field_name}PhaseShift,",
            f"    setPositionMode := dev.{field_name}SetPositionMode,",
            f"    overrideEnable := dev.{field_name}OverrideEnable,",
            f"    velFactor := dev.{field_name}VelFactor,",
            f"    accFactor := dev.{field_name}AccFactor,",
            f"    jerkFactor := dev.{field_name}JerkFactor,",
            f"    jogForward := dev.{field_name}JogForward,",
            f"    jogBackward := dev.{field_name}JogBackward,",
            f"    reset := dev.{field_name}Reset,",
            f"    parameterNumber := dev.{field_name}ParameterNumber,",
            f"    parameterValue := dev.{field_name}ParameterValue,",
            f"    parameterBoolValue := dev.{field_name}ParameterBoolValue,",
            f"    touchProbeWindow := dev.{field_name}TouchProbeWindow,",
            f"    touchProbeFirst := dev.{field_name}TouchProbeFirst,",
            f"    touchProbeLast := dev.{field_name}TouchProbeLast);",
        ]
    )
    return declarations, call


def render_axis_group_block(field_name: str, device_label: str) -> tuple[list[str], str]:
    declarations = [
        f"    {field_name}Group : SM3_Robotics.AXIS_GROUP_REF_SM3;",
        f"    {field_name}GroupEnable : BOOL;",
        f"    {field_name}AxisGroupId : STRING;",
        f"    {field_name}AxisGroupName : STRING;",
        f"    {field_name}Cmd : AxisGroupCmd := AxisGroupCmd.Idle;",
        f"    {field_name}EndPoint : SM3_Robotics.SMC_POS_REF;",
        f"    {field_name}AuxPoint : SM3_Robotics.SMC_POS_REF;",
        f"    {field_name}CircMode : SM3_Robotics.SMC_CIRC_MODE := SM3_Robotics.SMC_CIRC_MODE.BORDER;",
        f"    {field_name}PathChoice : SM3_Robotics.MC_CIRC_PATHCHOICE := SM3_Robotics.MC_CIRC_PATHCHOICE.CLOCKWISE;",
        f"    {field_name}Velocity : LREAL;",
        f"    {field_name}Acceleration : LREAL;",
        f"    {field_name}Deceleration : LREAL;",
        f"    {field_name}Jerk : LREAL;",
        f"    {field_name}CoordinateSystem : SM3_Robotics.SMC_COORD_SYSTEM := SM3_Robotics.SMC_COORD_SYSTEM.MCS;",
        f"    {field_name}BufferMode : SM3_Basic.MC_BUFFER_MODE := SM3_Basic.MC_BUFFER_MODE.aborting;",
        f"    {field_name}TransitionMode : SM3_Robotics.MC_TRANSITION_MODE := SM3_Robotics.MC_TRANSITION_MODE.TMNone;",
        f"    {field_name}TransitionParameter : LREAL := 0.0;",
        f"    {field_name}OverrideEnable : BOOL;",
        f"    {field_name}VelFactor : REAL := 1.0;",
        f"    {field_name}AccFactor : REAL := 1.0;",
        f"    {field_name}JerkFactor : REAL := 1.0;",
        f"    {field_name}Reset : BOOL;",
        f"    {field_name} : AxisGroup;",
    ]
    call = "\n".join(
        [
            f"(* {device_label} *)",
            f"dev.{field_name}(",
            f"    group := dev.{field_name}Group,",
            f"    groupEnable := dev.{field_name}GroupEnable,",
            f"    axisGroupId := dev.{field_name}AxisGroupId,",
            f"    axisGroupName := dev.{field_name}AxisGroupName,",
            f"    cmd := dev.{field_name}Cmd,",
            f"    endPoint := dev.{field_name}EndPoint,",
            f"    auxPoint := dev.{field_name}AuxPoint,",
            f"    circMode := dev.{field_name}CircMode,",
            f"    pathChoice := dev.{field_name}PathChoice,",
            f"    velocity := dev.{field_name}Velocity,",
            f"    acceleration := dev.{field_name}Acceleration,",
            f"    deceleration := dev.{field_name}Deceleration,",
            f"    jerk := dev.{field_name}Jerk,",
            f"    coordinateSystem := dev.{field_name}CoordinateSystem,",
            f"    bufferMode := dev.{field_name}BufferMode,",
            f"    transitionMode := dev.{field_name}TransitionMode,",
            f"    transitionParameter := dev.{field_name}TransitionParameter,",
            f"    overrideEnable := dev.{field_name}OverrideEnable,",
            f"    velFactor := dev.{field_name}VelFactor,",
            f"    accFactor := dev.{field_name}AccFactor,",
            f"    jerkFactor := dev.{field_name}JerkFactor,",
            f"    reset := dev.{field_name}Reset);",
        ]
    )
    return declarations, call


def render_signal_mgmt_block(field_name: str, device_label: str) -> tuple[list[str], str]:
    declarations = [
        f"    {field_name}Code : WORD;",
        f"    {field_name}Category : SignalCategory := SignalCategory.Information;",
        f"    {field_name}ResetPol : ResetPolicy := ResetPolicy.UnconditionedReset;",
        f"    {field_name}OutputAction : SignalOutputAction := SignalOutputAction.None;",
        f"    {field_name}ActivationCondition : BOOL;",
        f"    {field_name}AutoResetCondition : BOOL;",
        f"    {field_name}Reset : BOOL;",
        f"    {field_name}AuxReset : BOOL;",
        f"    {field_name}SelectiveResetTrigger : BOOL;",
        f"    {field_name}SelectiveResetCode : WORD;",
        f"    {field_name}LoggerName : STRING;",
    ]
    if field_name != "signalMgmt":
        declarations.append(f"    {field_name} : SignalMgmt;")
    target = field_name
    call = "\n".join(
        [
            f"(* {device_label} *)",
            f"dev.{target}(",
            "    operationType := SignalMgmtOperatingMode.Process,",
            f"    code := dev.{field_name}Code,",
            f"    category := dev.{field_name}Category,",
            f"    resetPol := dev.{field_name}ResetPol,",
            f"    outputAction := dev.{field_name}OutputAction,",
            f"    activationCondition := dev.{field_name}ActivationCondition,",
            f"    autoResetCondition := dev.{field_name}AutoResetCondition,",
            f"    reset := dev.{field_name}Reset,",
            f"    auxReset := dev.{field_name}AuxReset,",
            f"    selectiveResetTrigger := dev.{field_name}SelectiveResetTrigger,",
            f"    selectiveResetCode := dev.{field_name}SelectiveResetCode,",
            f"    loggerName := dev.{field_name}LoggerName);",
        ]
    )
    return declarations, call


def render_atomic_device_blocks(
    root_device_id: str,
    devices: dict[str, DeviceDef],
    physical_devices: dict[str, PhysicalDeviceRec],
    parameters: dict[str, ParameterRec],
    parameter_defs: dict[str, ParameterDefRec],
) -> tuple[str, str]:
    declarations: list[str] = []
    calls: list[str] = []
    scope_ids = subtree_device_ids(root_device_id, devices) - {root_device_id}
    children = sorted(
        (devices[device_id] for device_id in scope_ids if infer_atomic_kind(devices[device_id])),
        key=lambda row: row.device_id,
    )
    if not children:
        return (
            "    (* No supported atomic device instances found below the Application scope root. *)",
            "(* No supported atomic devices found below the application root Device. *)",
        )

    seen_field_names: dict[str, str] = {}
    for device in children:
        fb_kind = infer_atomic_kind(device)
        field_name = logical_device_name(device, physical_devices)
        previous_device_id = seen_field_names.get(field_name)
        if previous_device_id and previous_device_id != device.device_id:
            fail_validation(
                [
                    "Atomic device naming collisions detected after IEC normalization:",
                    f"{field_name} <- {previous_device_id}, {device.device_id}",
                ]
            )
        seen_field_names[field_name] = device.device_id
        device_label = field_name[:1].upper() + field_name[1:]
        if fb_kind == "Actuator":
            append_unique(
                declarations,
                f"    {field_name}EnableRequest : BOOL;",
                f"    {field_name}DisableRequest : BOOL;",
                f"    {field_name}ActuatorId : STRING;",
                f"    {field_name}ActuatorName : STRING;",
                f"    {field_name}ActuationType : ActuatorActuationType;",
                f"    {field_name}FeedbackType : ActuatorFeedbackType;",
                f"    {field_name}Model : ActuatorModel;",
                f"    {field_name}EnableTime : UINT;",
                f"    {field_name}DisableTime : UINT;",
                f"    {field_name}EnablePreset : BOOL := FALSE;",
                f"    {field_name}DiagnosticsEnable : BOOL := TRUE;",
                f"    {field_name}EnabledSensor : BOOL;",
                f"    {field_name}DisabledSensor : BOOL;",
                f"    {field_name}ExternalFault : BOOL;",
                f"    {field_name}Ref : REAL;",
                f"    {field_name}Feedback : REAL;",
                f"    {field_name} : Actuator;",
            )
            calls.append(
                "\n".join(
                    [
                        f"(* {device_label} *)",
                        f"dev.{field_name}(",
                        f"    enableRequest := dev.{field_name}EnableRequest,",
                        f"    disableRequest := dev.{field_name}DisableRequest,",
                        f"    actuatorId := dev.{field_name}ActuatorId,",
                        f"    actuatorName := dev.{field_name}ActuatorName,",
                        f"    actuationType := dev.{field_name}ActuationType,",
                        f"    feedbackType := dev.{field_name}FeedbackType,",
                        f"    model := dev.{field_name}Model,",
                        "    operationType := operationType,",
                        "    clock := clks.clock100ms,",
                        f"    enableTime := dev.{field_name}EnableTime,",
                        f"    disableTime := dev.{field_name}DisableTime,",
                        f"    enablePreset := dev.{field_name}EnablePreset,",
                        f"    diagnosticsEnable := dev.{field_name}DiagnosticsEnable,",
                        f"    enabledSensor := dev.{field_name}EnabledSensor,",
                        f"    disabledSensor := dev.{field_name}DisabledSensor,",
                        f"    externalFault := dev.{field_name}ExternalFault,",
                        f"    ref := dev.{field_name}Ref,",
                        f"    feedback := dev.{field_name}Feedback);",
                    ]
                )
            )
        elif fb_kind == "ProcessPid":
            setpoint_field, feedback_field = infer_process_pid_fields(
                root_device_id, device, physical_devices, parameters, parameter_defs
            )
            append_unique(
                declarations,
                f"    {field_name}Enable : BOOL;",
                f"    {field_name}Reset : BOOL;",
                f"    {field_name}ControlSystemId : STRING;",
                f"    {field_name}ControlSystemName : STRING;",
                f"    {field_name}FeedbackMultiplier : REAL := 1.0;",
                f"    {field_name}AtSetpointHysteresis : REAL;",
                f"    {field_name}SetpointMultiplier : REAL := 1.0;",
                f"    {field_name}SetpointMin : REAL;",
                f"    {field_name}SetpointMax : REAL;",
                f"    {field_name}SetpointRampType : RampType := RampType.Linear;",
                f"    {field_name}SetpointIncreaseTime : TIME := T#0s;",
                f"    {field_name}SetpointDecreaseTime : TIME := T#0s;",
                f"    {field_name}SetpointFreezeEnable : BOOL;",
                f"    {field_name}DeviationInversion : BOOL;",
                f"    {field_name}OutputMin : REAL;",
                f"    {field_name}OutputMax : REAL;",
                f"    {field_name}OutputFreezeEnable : BOOL;",
                f"    {field_name}Gain : REAL := 1.0;",
                f"    {field_name}IntegrationTime : REAL := 0.0;",
                f"    {field_name}DerivationTime : REAL := 0.0;",
                f"    {field_name}Offset : REAL := 0.0;",
                f"    {field_name}DeadbandRange : REAL;",
                f"    {field_name}DeadbandDelay : TIME;",
                f"    {field_name}SleepLevel : REAL := 0.0;",
                f"    {field_name}SleepDelay : TIME;",
                f"    {field_name}WakeupDeviation : REAL;",
                f"    {field_name}WakeupDelay : TIME;",
                f"    {field_name}SleepBoostLevel : REAL := 0.0;",
                f"    {field_name}SleepBoostTime : TIME;",
                f"    {field_name}TrackingMode : BOOL := FALSE;",
                f"    {field_name}TrackingRef : REAL := 0.0;",
                f"    {field_name}TickTime : TIME := T#10ms;",
                f"    {field_name}SetpointEpsilon : REAL := 0.000001;",
                f"    {field_name} : ProcessPid;",
            )
            feedback_expr = f"dev.{feedback_field}" if feedback_field else "0.0"
            setpoint_expr = f"dev.{setpoint_field}" if setpoint_field else "0.0"
            calls.append(
                "\n".join(
                    [
                        f"(* {device_label} *)",
                        f"dev.{field_name}(",
                        f"    enable := dev.{field_name}Enable,",
                        f"    reset := dev.{field_name}Reset,",
                        f"    controlSystemId := dev.{field_name}ControlSystemId,",
                        f"    controlSystemName := dev.{field_name}ControlSystemName,",
                        f"    feedback := {feedback_expr},",
                        f"    feedbackMultiplier := dev.{field_name}FeedbackMultiplier,",
                        f"    setpoint := {setpoint_expr},",
                        f"    atSetpointHysteresis := dev.{field_name}AtSetpointHysteresis,",
                        f"    setpointMultiplier := dev.{field_name}SetpointMultiplier,",
                        f"    setpointMin := dev.{field_name}SetpointMin,",
                        f"    setpointMax := dev.{field_name}SetpointMax,",
                        f"    setpointRampType := dev.{field_name}SetpointRampType,",
                        f"    setpointIncreaseTime := dev.{field_name}SetpointIncreaseTime,",
                        f"    setpointDecreaseTime := dev.{field_name}SetpointDecreaseTime,",
                        f"    setpointFreezeEnable := dev.{field_name}SetpointFreezeEnable,",
                        f"    deviationInversion := dev.{field_name}DeviationInversion,",
                        f"    outputMin := dev.{field_name}OutputMin,",
                        f"    outputMax := dev.{field_name}OutputMax,",
                        f"    outputFreezeEnable := dev.{field_name}OutputFreezeEnable,",
                        f"    gain := dev.{field_name}Gain,",
                        f"    integrationTime := dev.{field_name}IntegrationTime,",
                        f"    derivationTime := dev.{field_name}DerivationTime,",
                        f"    offset := dev.{field_name}Offset,",
                        f"    deadbandRange := dev.{field_name}DeadbandRange,",
                        f"    deadbandDelay := dev.{field_name}DeadbandDelay,",
                        f"    sleepLevel := dev.{field_name}SleepLevel,",
                        f"    sleepDelay := dev.{field_name}SleepDelay,",
                        f"    wakeupDeviation := dev.{field_name}WakeupDeviation,",
                        f"    wakeupDelay := dev.{field_name}WakeupDelay,",
                        f"    sleepBoostLevel := dev.{field_name}SleepBoostLevel,",
                        f"    sleepBoostTime := dev.{field_name}SleepBoostTime,",
                        f"    trackingMode := dev.{field_name}TrackingMode,",
                        f"    trackingRef := dev.{field_name}TrackingRef,",
                        # clock10ms matches the field's own compiled-in default
                        # (TickTime : TIME := T#10ms declared above). ProcessPid's
                        # ramp math assumes 'clock' pulses at exactly the period
                        # given by 'tickTime', so if a recipe overrides tickTime
                        # to something other than 10ms, this line must be updated
                        # by hand to the matching clks.clockXXms symbol -- there
                        # is no generic/parametrized timebase in Clocks to derive
                        # this from the recipe value automatically.
                        "    clock := clks.clock10ms,",
                        f"    tickTime := dev.{field_name}TickTime,",
                        f"    setpointEpsilon := dev.{field_name}SetpointEpsilon);",
                    ]
                )
            )
        elif fb_kind == "ActuatorGroup":
            new_declarations, call = render_actuator_group_block(field_name, device_label)
            append_unique(declarations, *new_declarations)
            calls.append(call)
        elif fb_kind == "Axis":
            new_declarations, call = render_axis_block(field_name, device_label)
            append_unique(declarations, *new_declarations)
            calls.append(call)
        elif fb_kind == "AxisGroup":
            new_declarations, call = render_axis_group_block(field_name, device_label)
            append_unique(declarations, *new_declarations)
            calls.append(call)
        elif fb_kind == "SignalMgmt":
            new_declarations, call = render_signal_mgmt_block(field_name, device_label)
            append_unique(declarations, *new_declarations)
            calls.append(call)
        else:
            calls.append(
                f"(* TODO: infer atomic FB type for child device {device.device_id} from DeviceType/ControlMethod *)"
            )

    return "\n".join(declarations), "\n\n".join(calls)


def extract_declared_field_names(block: str) -> frozenset[str]:
    """Field names already declared by a rendered DUT block (e.g. the atomic
    device block). Used to keep render_parameter_declarations() from
    re-declaring the same STRUCT member a second time with a different
    (generic) type -- invalid IEC 61131-3."""
    names: set[str] = set()
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("(*"):
            continue
        if " : " not in stripped:
            continue
        names.add(stripped.split(" : ", 1)[0])
    return frozenset(names)


def render_blocking_device_signal_rules(
    root_device_id: str,
    devices: dict[str, DeviceDef],
    physical_devices: dict[str, PhysicalDeviceRec],
) -> str:
    lines: list[str] = []
    scope_ids = subtree_device_ids(root_device_id, devices) - {root_device_id}
    for device in sorted((devices[device_id] for device_id in scope_ids), key=lambda row: row.device_id):
        fb_kind = infer_atomic_kind(device)
        if not fb_kind:
            continue
        field_name = logical_device_name(device, physical_devices)
        comment_name = field_name[:1].upper() + field_name[1:]
        if fb_kind == "Actuator":
            lines.extend(
                [
                    f"(* {comment_name} blocking diagnostics *)",
                    f"dev.signalMgmt(code := 100, category := SignalCategory.Alarm, outputAction := SignalOutputAction.ImmediateStop, activationCondition := dev.{field_name}.fault, loggerName := dev.signalMgmt.loggerName);",
                ]
            )
        elif fb_kind == "ProcessPid":
            lines.extend(
                [
                    f"(* {comment_name} blocking diagnostics *)",
                    f"dev.signalMgmt(code := 110, category := SignalCategory.Alarm, outputAction := SignalOutputAction.ImmediateStop, activationCondition := dev.{field_name}.invalidConfig, loggerName := dev.signalMgmt.loggerName);",
                ]
            )
        elif fb_kind == "ActuatorGroup":
            lines.extend(
                [
                    f"(* {comment_name} blocking diagnostics *)",
                    f"dev.signalMgmt(code := 120, category := SignalCategory.Alarm, outputAction := SignalOutputAction.ImmediateStop, activationCondition := dev.{field_name}.invalidConfig OR dev.{field_name}.underMinimum, loggerName := dev.signalMgmt.loggerName);",
                ]
            )
        elif fb_kind == "Axis":
            lines.extend(
                [
                    f"(* {comment_name} blocking diagnostics *)",
                    f"dev.signalMgmt(code := 130, category := SignalCategory.Alarm, outputAction := SignalOutputAction.ImmediateStop, activationCondition := dev.{field_name}.axisError OR dev.{field_name}.cmdError, loggerName := dev.signalMgmt.loggerName);",
                ]
            )
        elif fb_kind == "AxisGroup":
            lines.extend(
                [
                    f"(* {comment_name} blocking diagnostics *)",
                    f"dev.signalMgmt(code := 140, category := SignalCategory.Alarm, outputAction := SignalOutputAction.ImmediateStop, activationCondition := dev.{field_name}.groupError OR dev.{field_name}.cmdError, loggerName := dev.signalMgmt.loggerName);",
                ]
            )
        elif fb_kind == "SignalMgmt":
            lines.extend(
                [
                    f"(* {comment_name} blocking diagnostics *)",
                    f"dev.signalMgmt(code := 150, category := SignalCategory.Alarm, outputAction := SignalOutputAction.ImmediateStop, activationCondition := dev.{field_name}.error, loggerName := dev.signalMgmt.loggerName);",
                ]
            )
    if not lines:
        return "(* No blocking-device diagnostics rules derived for this Application scope. *)"
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render DeviceFacade and IOFacade from Moqui seed XML data")
    parser.add_argument("xml", nargs="+", type=Path, help="One or more Moqui seed XML files")
    parser.add_argument("--device-id", required=True, help="Device ID to render")
    parser.add_argument("--component-name", required=True, help="Component/machine name used under output/")
    parser.add_argument("--namespace", default="mantle", help="Top-level PLC namespace folder under src/main")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "output",
        help="Root output directory",
    )
    parser.add_argument(
        "--templates-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "references" / "plc-codegen-templates",
        help="Directory containing *.template.* files",
    )
    parser.add_argument("--request-map", type=Path, help="Optional JSON file mapping state names to request fields")
    parser.add_argument(
        "--session-dir",
        type=Path,
        help="Saved session directory; if provided, default output goes to generated-plc/ and session.json is updated",
    )
    parser.add_argument("--output-root-override", type=Path, help="Explicit output root while retaining session validation")
    parser.add_argument("--allow-logical-root", action="store_true", help="Allow a subsystem DeviceGroup as the Application scope root")
    args = parser.parse_args()
    if args.session_dir:
        validate_upstream_surveys(args.session_dir.resolve())

    devices, physical_devices, parameter_defs, parameters, device_requests, request_items, status_items, flow_item_initial = parse_seed_files(args.xml)
    validate_seed_graph(
        args.device_id,
        devices,
        physical_devices,
        parameter_defs,
        parameters,
        device_requests,
        request_items,
        status_items,
        flow_item_initial,
        require_physical_root=not args.allow_logical_root,
    )
    device = devices.get(args.device_id)
    if not device:
        raise SystemExit(f"Device {args.device_id} not found in provided XML files")

    statusflow_items = parse_statusflow_items(device.statusflow_id, status_items, flow_item_initial)
    initial_enum = statusflow_items[0].enum_name if statusflow_items else "Standby"
    request_map = load_request_map(args.request_map)
    device_scope = subtree_device_ids(args.device_id, devices)

    # Render the atomic-device block first: it declares the full native-typed
    # signature of each FB instance (e.g. ProcessPid's SetpointRampType as
    # RampType, not a generic DINT). render_parameter_declarations() must
    # skip those same field names below it would otherwise re-declare them
    # with a generic type -- an invalid duplicate STRUCT member.
    atomic_declarations, device_manager_calls = render_atomic_device_blocks(
        args.device_id, devices, physical_devices, parameters, parameter_defs
    )
    atomic_field_names = extract_declared_field_names(atomic_declarations)

    analog_decl, digital_decl = render_parameter_declarations(
        args.device_id, device_scope, devices, physical_devices, parameters, parameter_defs,
        exclude_field_names=atomic_field_names,
    )
    physical_inputs, physical_outputs = render_io_declarations(
        device_scope, request_items, device_requests, parameter_defs, parameters
    )
    state_request_declarations = render_state_request_declarations(statusflow_items, request_map)

    replacements = {
        "${MAIN_STATUS_ENUM}": "MainStatus",
        "${INITIAL_STATUS}": f"MainStatus.{initial_enum}",
        "${ANALOG_SIGNAL_DECLARATIONS}": analog_decl,
        "${DIGITAL_SIGNAL_DECLARATIONS}": digital_decl,
        "${PREDICATE_DECLARATIONS}": "    (* Project predicates are generated from reviewed FSM surveys. *)",
        "${PROCESS_MODE_DECLARATIONS}": "    (* Project-specific process fields are declared through explicit seed parameters. *)",
        "${SUBSYSTEM_FSM_DECLARATIONS}": "    (* Subsystem FSM state fields are generated by render_codesys_applications.py. *)",
        "${STATE_REQUEST_DECLARATIONS}": state_request_declarations or "    standbyRequest : BOOL;",
        "${ATOMIC_DEVICE_DECLARATIONS}": atomic_declarations,
        "${PHYSICAL_INPUT_DECLARATIONS}": physical_inputs,
        "${PHYSICAL_OUTPUT_DECLARATIONS}": physical_outputs,
        "${DEVICE_MANAGER_CALLS}": device_manager_calls,
        "${BLOCKING_DEVICE_SIGNAL_RULES}": render_blocking_device_signal_rules(
            args.device_id, devices, physical_devices
        ),
        "${SAFETY_SIGNAL_RULES}": "(* Safety logic is external; only modeled fault/stop indications are observed here. *)",
    }

    output_root = resolve_output_root(args)
    paths = output_paths(output_root, args.namespace, normalize_component_name(args.component_name))
    write_rendered(load_template(args.templates_dir / "DeviceFacade.template.dut"), replacements, paths["DeviceFacade.dut"])
    write_rendered(load_template(args.templates_dir / "IOFacade.template.dut"), replacements, paths["IOFacade.dut"])
    write_rendered(load_template(args.templates_dir / "DeviceManager.template.pou"), replacements, paths["DeviceManager.pou"])
    write_rendered(load_template(args.templates_dir / "DeviceDiagnostics.template.pou"), replacements, paths["DeviceDiagnostics.pou"])
    if args.session_dir:
        update_session_metadata(args.session_dir.resolve(), paths["component_root"].resolve())
    print(f"Rendered device catalogs for {args.device_id} into {paths['component_root']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

PLANT_SCRIPT_DIR = Path(__file__).resolve().parents[2] / "moqui-plant-designer" / "scripts"
if str(PLANT_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(PLANT_SCRIPT_DIR))
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from survey_validation import (
    load_fsm_survey_model,
    load_upstream_survey_model,
    validate_fsm_surveys,
    validate_upstream_surveys,
    _gateway_row_is_meaningful,
    _gateway_transport_row_is_meaningful,
    _plc4j_connection_row_is_meaningful,
    _normalize_transport_scope,
)
from render_atomic_component_template import compose_seed, derive_defaults, load_catalog


LOGICAL_MODEL_TO_DEVICE_TYPE = {
    "Actuator": "DtMoquiPlcActuator",
    "ActuatorGroup": "DtMoquiPlcActuatorGroup",
    "ProcessPid": "DtMoquiPlcProcessPID",
    "Axis": "DtMoquiPlcAxis",
    "AxisGroup": "DtMoquiPlcAxisGroup",
    "SignalMgmt": "DtMoquiPlcSignalMgmt",
}
LOGICAL_MODEL_TO_LIBRARY_COMPONENT = {
    "Actuator": "actuator",
    "ActuatorGroup": "actuator_group",
    "ProcessPid": "process_pid",
    "Axis": "axis",
    "AxisGroup": "axis_group",
    "SignalMgmt": "signal_mgmt",
}

SUBSYSTEM_GROUP_DEVICE_TYPE = "DgtSubsystem"
DEFAULT_GATEWAY_DEVICE_TYPE_ENUM_ID = "DtEdgeGateway"
DEFAULT_SUBSYSTEM_MEMBER_PURPOSE_ENUM_ID = "DgmpSubsystem"
DEFAULT_CONTROLLED_DEVICE_MEMBER_PURPOSE_ENUM_ID = "DgmpControlledDevice"
DEFAULT_PROCESS_PLC_MEMBER_PURPOSE_ENUM_ID = "DgmpProcessPLC"

ACTUATION_CLASS_TO_CONTROL_METHOD = {
    "DA-DF": "DcmDoubleActuationDoubleFeedback",
    "SA-DF": "DcmSingleActuationDoubleFeedback",
    "SA-SAFD": "DcmSingleActuationEnableFeedback",
    "SA-SDFD": "DcmSingleActuationDisableFeedback",
    "SA-NO": "DcmSingleActuationNoFeedback",
}

IEC_TO_PARAMETER_TYPE = {
    "BOOL": "PtTextIndicator",
    "BYTE": "PtByte",
    "WORD": "PtBitSet",
    "DWORD": "PtBitSet",
    "LWORD": "PtBitSet",
    "INT": "PtNumberInteger",
    "UINT": "PtNumberInteger",
    "DINT": "PtNumberInteger",
    "UDINT": "PtNumberInteger",
    "REAL": "PtNumberDecimal",
    "LREAL": "PtNumberDecimal",
    "TIME": "PtTime",
    "STRING": "PtText",
}

IEC_TO_REQUEST_ITEM_TYPE = {
    "BOOL": "DritBool",
    "BYTE": "DritByte",
    "WORD": "DritWord",
    "DWORD": "DritDWord",
    "LWORD": "DritLWord",
    "INT": "DritInt",
    "UINT": "DritUInt",
    "DINT": "DritDInt",
    "UDINT": "DritUDInt",
    "REAL": "DritReal",
    "LREAL": "DritLReal",
}

DEFAULT_GATEWAY_ROUTER_ENUM_ID = "DrrMoquiDeviceGateway"
DEFAULT_PLC4J_ROUTER_ENUM_ID = "DrrDirect"
DEFAULT_LOG_TOPIC = "moqui-plc"
GATEWAY_RUN_SERVICE = "moqui.device.DeviceGatewayServices.run#GatewayDeviceRequest"
PLC4J_RUN_SERVICE = "moqui.plc4j.Plc4jServices.run#Plc4jRequest"
_start = Path(__file__).resolve()
_repo_dir = None
for _p in _start.parents:
    if (_p / "moqui-device").is_dir():
        _repo_dir = _p
        break
if _repo_dir is None:
    _repo_dir = _start.parents[5] if len(_start.parents) > 5 else _start.parents[4]
REPOSITORIES_DIR = _repo_dir
DEFAULT_MOQUI_DEVICE_DATA_PATH = REPOSITORIES_DIR / "moqui-device" / "data" / "DeviceData.xml"
DEFAULT_MOQUI_DEVICE_ENTITY_PATH = REPOSITORIES_DIR / "moqui-device" / "entity" / "DeviceEntities.xml"
DEFAULT_MOQUI_MATH_ENTITY_PATH = REPOSITORIES_DIR / "moqui-math" / "entity" / "MathEntities.xml"
ATOMIC_COMPONENT_LIBRARY_PATH = Path(__file__).resolve().parent.parent / "references" / "atomic-component-library.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_identifier(raw: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", raw.strip()).strip("_")
    if not cleaned:
        return "UNSPECIFIED"
    return cleaned.upper()


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].split(".")[-1]


def title_case(raw: str) -> str:
    parts = re.findall(r"[A-Za-z0-9]+", raw)
    if not parts:
        return "Value"
    return "".join(part[:1].upper() + part[1:] for part in parts)


def infer_root_device_id(model: dict, session_dir: Path) -> str:
    machine_name = model["project_scope"].get("machine_name") or session_dir.name
    return normalize_identifier(machine_name) + "_PLC"


def subsystem_group_device_id(subsystem_id: str) -> str:
    return f"DG_{normalize_identifier(subsystem_id)}"


def device_type_for_logical_model(logical_model: str) -> str:
    try:
        return LOGICAL_MODEL_TO_DEVICE_TYPE[logical_model]
    except KeyError as exc:
        raise SystemExit(
            f"Unsupported logical_model {logical_model}. Extend the supported model catalog before generating seed data."
        ) from exc


def library_component_for_logical_model(logical_model: str) -> str:
    try:
        return LOGICAL_MODEL_TO_LIBRARY_COMPONENT[logical_model]
    except KeyError as exc:
        raise SystemExit(
            f"Unsupported logical_model {logical_model}. Extend the atomic component library before generating seed data."
        ) from exc


def default_control_method_for_device(device: dict, atomic_library: dict) -> str:
    explicit = device.get("control_method_enum_id", "")
    if explicit:
        return explicit
    feedback_class = device.get("actuation_feedback_class", "")
    if feedback_class:
        derived = ACTUATION_CLASS_TO_CONTROL_METHOD.get(feedback_class, "")
        if derived:
            return derived
    component_key = library_component_for_logical_model(device["logical_model"])
    return atomic_library["components"][component_key].get("defaultControlMethodEnumId", "")


def parameter_type_for_signal(signal: dict) -> str:
    iec_type = signal["iec_type"].upper()
    try:
        return IEC_TO_PARAMETER_TYPE[iec_type]
    except KeyError as exc:
        raise SystemExit(
            f"Unsupported iec_type {signal['iec_type']} for parameter generation."
        ) from exc


def request_item_type_for_signal(signal: dict) -> str:
    iec_type = signal["iec_type"].upper()
    try:
        return IEC_TO_REQUEST_ITEM_TYPE[iec_type]
    except KeyError as exc:
        raise SystemExit(
            f"Unsupported iec_type {signal['iec_type']} for DeviceRequestItem generation."
        ) from exc


def purpose_for_signal(signal: dict) -> str:
    direction = signal["direction"].lower()
    if direction == "output":
        return "PpControl"
    if direction == "input":
        return "PpFeedback"
    raise SystemExit(f"Unsupported signal direction {signal['direction']}.")


def default_value_attrs(parameter_type_enum_id: str, direction: str) -> dict[str, str]:
    if parameter_type_enum_id == "PtTextIndicator":
        return {"symbolicValue": "N"}
    if parameter_type_enum_id in {"PtNumberInteger", "PtNumberDecimal", "PtTime", "PtByte", "PtBitSet"}:
        return {"numericValue": "0"}
    if parameter_type_enum_id in {"PtText"}:
        return {"symbolicValue": ""}
    return {"symbolicValue": "N" if direction.lower() == "input" else "N"}


def parse_iec_time_to_ms(value: str) -> str:
    match = re.fullmatch(r"T#(\d+)(ms|s|m)", value.strip(), re.IGNORECASE)
    if not match:
        return "100"
    amount = int(match.group(1))
    unit = match.group(2).lower()
    if unit == "ms":
        return str(amount)
    if unit == "s":
        return str(amount * 1000)
    if unit == "m":
        return str(amount * 60000)
    return "100"


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
        output_name = args.output_name or "survey-derived-seed.xml"
        return session_path.parent / seed_data_dir_name / output_name
    raise SystemExit("Provide --output or --session-dir")


def update_session_metadata(session_dir: Path, output_path: Path) -> None:
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
    step = steps.setdefault("seed_design", {"status": "pending", "notes": ""})
    step["status"] = "generated"
    step["notes"] = "Generated survey-derived seed draft from upstream engineering surveys; review entity IDs, enums, and request semantics."
    session_path.write_text(json.dumps(session, indent=2) + "\n", encoding="utf-8")


def add_elem(parent: ET.Element, tag: str, **attrs: str) -> ET.Element:
    cleaned = {key: value for key, value in attrs.items() if value != ""}
    return ET.SubElement(parent, tag, cleaned)


def append_statusflow_seed(root: ET.Element, fsm_model: dict) -> dict[str, dict]:
    """Materialize only FSM topology. Predicates, actions, and call order stay in PLC code."""
    fsms = fsm_model.get("fsms", [])
    by_fsm_id = {fsm["fsm_id"]: fsm for fsm in fsms}
    owner_map: dict[str, dict] = {}
    emitted_statuses: dict[str, tuple[str, str]] = {}
    for fsm in fsms:
        owner_map[fsm["owner_subsystem_id"]] = fsm
        add_elem(
            root,
            "moqui.basic.StatusType",
            statusTypeId=fsm["status_type_id"],
            description=f"Status type for {fsm['component_name']}.",
        )
        parent_flow_id = ""
        if fsm["parent_fsm_id"]:
            parent_flow_id = by_fsm_id[fsm["parent_fsm_id"]]["status_flow_id"]
        add_elem(
            root,
            "moqui.basic.StatusFlow",
            statusFlowId=fsm["status_flow_id"],
            statusTypeId=fsm["status_type_id"],
            parentStatusFlowId=parent_flow_id,
            description=fsm["notes"] or f"Survey-derived FSM for {fsm['component_name']}.",
        )
        for state in sorted(fsm["states"], key=lambda item: (item["sequence"], item["status_id"])):
            signature = (fsm["status_type_id"], state["name"])
            previous = emitted_statuses.get(state["status_id"])
            if previous and previous != signature:
                raise SystemExit(
                    f"Global StatusItem ID {state['status_id']} is reused with conflicting type/name; use globally stable status IDs."
                )
            if not previous:
                add_elem(
                    root,
                    "moqui.basic.StatusItem",
                    statusId=state["status_id"],
                    statusTypeId=fsm["status_type_id"],
                    sequenceNum=str(state["sequence"]),
                    description=state["name"],
                )
                emitted_statuses[state["status_id"]] = signature
            add_elem(
                root,
                "moqui.basic.StatusFlowItem",
                statusFlowId=fsm["status_flow_id"],
                statusId=state["status_id"],
                isInitial="Y" if state["initial"] else "N",
            )
        for transition in sorted(
            fsm["transitions"], key=lambda item: (item["from_status_id"], item["precedence"], item["to_status_id"])
        ):
            target_fsm = by_fsm_id[transition["to_fsm_id"] or fsm["fsm_id"]]
            add_elem(
                root,
                "moqui.basic.StatusFlowTransition",
                statusFlowId=fsm["status_flow_id"],
                statusId=transition["from_status_id"],
                toStatusFlowId=target_fsm["status_flow_id"],
                toStatusId=transition["to_status_id"],
                transitionSequence=str(transition["precedence"]),
                transitionName=transition["name"] or f"{transition['from_status_id']} to {transition['to_status_id']}",
            )
    return owner_map


def load_enum_ids(xml_paths: list[Path]) -> set[str]:
    enum_ids: set[str] = set()
    for xml_path in xml_paths:
        if not xml_path.is_file():
            continue
        root = ET.parse(xml_path).getroot()
        for elem in root.iter():
            if elem.tag.endswith("Enumeration") and "enumId" in elem.attrib:
                enum_ids.add(elem.attrib["enumId"])
    return enum_ids


def validate_generated_enum_references(root: ET.Element, enum_ids: set[str]) -> None:
    enum_fields = {
        "deviceTypeEnumId",
        "purposeEnumId",
        "controlMethodEnumId",
        "connectionTypeEnumId",
        "driverEnumId",
        "transportEnumId",
        "requestTypeEnumId",
        "routerEnumId",
        "itemTypeEnumId",
        "parameterTypeEnumId",
    }
    missing: list[str] = []
    for elem in root.iter():
        for field_name in enum_fields:
            value = elem.attrib.get(field_name, "")
            if value and value not in enum_ids:
                missing.append(f"{local_name(elem.tag)}.{field_name}={value}")
    if missing:
        raise SystemExit(
            "Generated seed references enum IDs not found in canonical moqui-device/moqui-math catalogs:\n- "
            + "\n- ".join(sorted(set(missing)))
        )


def validate_generated_model_references(root: ET.Element) -> None:
    by_tag: dict[str, list[ET.Element]] = {}
    for element in root:
        if not isinstance(element.tag, str):
            continue
        by_tag.setdefault(local_name(element.tag), []).append(element)
    device_ids = {row.get("deviceId") for row in by_tag.get("Device", [])}
    config_ids = {row.get("deviceConfigId") for row in by_tag.get("DeviceConfig", [])}
    rule_set_ids = {row.get("deviceRuleSetId") for row in by_tag.get("DeviceRuleSet", [])}
    parameter_def_ids = {row.get("parameterDefId") for row in by_tag.get("ParameterDef", [])}
    parameter_ids = {row.get("parameterId") for row in by_tag.get("Parameter", []) if row.get("deviceId")}
    device_types = {row.get("deviceId"): row.get("deviceTypeEnumId") for row in by_tag.get("Device", [])}
    config_types = {row.get("deviceConfigId"): row.get("deviceTypeEnumId") for row in by_tag.get("DeviceConfig", [])}
    errors: list[str] = []
    for row in by_tag.get("PhysicalDevice", []):
        device_name = row.get("deviceName", "")
        if device_name == "dev" or device_name.startswith("dev."):
            errors.append(
                f"PhysicalDevice {row.get('deviceId')} stores IEC namespace in deviceName {device_name}; use the logical instance name only."
            )
    for row in by_tag.get("ParameterDef", []):
        parameter_name = row.get("parameterName", "")
        if parameter_name.startswith("dev."):
            errors.append(
                f"ParameterDef {row.get('parameterDefId')} stores IEC namespace in parameterName {parameter_name}."
            )
    for row in by_tag.get("DeviceGroupMember", []):
        if row.get("deviceId") not in device_ids or row.get("memberDeviceId") not in device_ids:
            errors.append(f"DeviceGroupMember {row.get('deviceId')} -> {row.get('memberDeviceId')} has an unknown Device.")
    for row in by_tag.get("Parameter", []):
        parameter_alias = row.get("parameterAlias", "")
        if parameter_alias.startswith("dev."):
            errors.append(
                f"Parameter {row.get('parameterId')} stores IEC namespace in parameterAlias {parameter_alias}."
            )
        if row.get("deviceConfigId") and row.get("parameterDefId") not in parameter_def_ids:
            errors.append(f"Config parameter {row.get('parameterId')} references unknown ParameterDef {row.get('parameterDefId')}.")
    for row in by_tag.get("DeviceRequestItem", []):
        if row.get("parameterId") not in parameter_ids:
            errors.append(
                f"DeviceRequestItem {row.get('requestName')}/{row.get('parameterId')} must reference an existing device-bound Parameter."
            )
    for row in by_tag.get("DeviceRule", []):
        config_id, device_id = row.get("deviceConfigId"), row.get("deviceId")
        if config_id not in config_ids or row.get("deviceRuleSetId") not in rule_set_ids:
            errors.append(f"DeviceRule {row.get('deviceRuleId')} has an unknown config or rule set.")
        elif device_types.get(device_id) != config_types.get(config_id):
            errors.append(
                f"DeviceRule {row.get('deviceRuleId')} type mismatch: target {device_id} is {device_types.get(device_id)}, "
                f"config {config_id} is {config_types.get(config_id)}."
            )
    if errors:
        raise SystemExit("Generated seed model validation failed:\n- " + "\n- ".join(errors))


def indent(elem: ET.Element, level: int = 0) -> None:
    i = "\n" + level * "    "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "    "
        for child in elem:
            indent(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = i
    elif level and (not elem.tail or not elem.tail.strip()):
        elem.tail = i


def request_name_for_transport(base_name: str, transport_tag: str, transport_count: int) -> str:
    if transport_count <= 1:
        return base_name
    return f"{base_name}_{title_case(transport_tag)}"


def transports_for_domain(domain: dict, transport_architecture: dict) -> list[str]:
    primary_mode = transport_architecture["primary_transport_mode"]
    if primary_mode == "gateway":
        return ["gateway"]
    if primary_mode == "plc4j":
        return ["plc4j"]

    normalized_scope = _normalize_transport_scope(domain.get("transport_projection", ""))
    if normalized_scope == "gateway":
        return ["gateway"]
    if normalized_scope == "plc4j":
        return ["plc4j"]
    if normalized_scope == "both":
        return ["gateway", "plc4j"]
    raise SystemExit(
        f"Hybrid transport architecture requires explicit transport_scope for domain {domain['domain_id']}."
    )


def resolve_plc4j_connection_for_domain(domain: dict, model: dict) -> dict:
    domain_id = domain["domain_id"]
    connections = [
        row for row in model["plc4j_connections"] if _plc4j_connection_row_is_meaningful(row)
    ]
    scoped_matches = [row for row in connections if domain_id in row["scoped_domain_ids"]]
    if len(scoped_matches) == 1:
        return scoped_matches[0]
    if len(scoped_matches) > 1:
        raise SystemExit(
            f"Sampling domain {domain_id} matches multiple plc4j_connections; keep domain-to-connection mapping unambiguous."
        )

    unscoped_matches = [row for row in connections if not row["scoped_domain_ids"]]
    if len(unscoped_matches) == 1:
        return unscoped_matches[0]
    if not unscoped_matches:
        raise SystemExit(
            f"Sampling domain {domain_id} requires plc4j transport but no plc4j_connection covers it."
        )
    raise SystemExit(
        f"Sampling domain {domain_id} matches multiple unscoped plc4j_connections; scope them explicitly by domain."
    )


def resolve_gateway_transport_for_domain(domain: dict, model: dict) -> dict:
    domain_id = domain["domain_id"]
    transports = [
        row for row in model["gateway_transports"] if _gateway_transport_row_is_meaningful(row)
    ]
    matches = [
        row for row in transports if domain_id in row["scoped_domain_ids"]
    ]
    if len(matches) != 1:
        raise SystemExit(
            f"Sampling domain {domain_id} must resolve to exactly one gateway_transport; found {len(matches)}."
        )
    return matches[0]


def gateway_by_id(model: dict, gateway_device_id: str) -> dict:
    matches = [
        row for row in model["gateways"]
        if _gateway_row_is_meaningful(row) and row["gateway_device_id"] == gateway_device_id
    ]
    if len(matches) != 1:
        raise SystemExit(f"Gateway device {gateway_device_id} must resolve to exactly one gateway topology row.")
    return matches[0]


def controller_for_domain(model: dict, domain_id: str, fallback: str) -> str:
    domain = next((row for row in model["domains"] if row["domain_id"] == domain_id), None)
    return domain["controller_device_id"] if domain and domain.get("controller_device_id") else fallback


def controller_for_device(model: dict, device_id: str, fallback: str) -> str:
    controllers = [row for row in model["controllers"] if row["controller_device_id"]]
    if len(controllers) == 1:
        return controllers[0]["controller_device_id"]
    device = next((row for row in model["devices"] if row["device_id"] == device_id), None)
    if not device:
        raise SystemExit(f"Cannot resolve controller for live parameter device {device_id}.")
    system_by_id = {row["subsystem_id"]: row for row in model["system_tree"]}
    subsystem_id = device["parent_subsystem_id"]
    while system_by_id[subsystem_id]["parent_subsystem_id"]:
        subsystem_id = system_by_id[subsystem_id]["parent_subsystem_id"]
    supervisor = next(
        (row for row in model.get("fsm_model", {}).get("fsms", []) if row["owner_subsystem_id"] == subsystem_id),
        None,
    )
    if supervisor:
        matches = [row for row in controllers if row["application_id"] == supervisor["application_id"]]
        if len(matches) == 1:
            return matches[0]["controller_device_id"]
    raise SystemExit(f"Live parameter device {device_id} does not resolve to exactly one controller/Application.")


def append_gateway_dispatch_wrapper(
    root: ET.Element,
    model: dict,
    field_request_name: str,
    request_type_enum_id: str,
    purpose_enum_id: str,
    transport: dict,
    connection_name: str = "",
) -> None:
    gateway = gateway_by_id(model, transport["gateway_device_id"])
    add_elem(
        root,
        "moqui.device.DeviceRequest",
        requestName=f"{field_request_name}_GatewayDispatch",
        deviceId=gateway["gateway_device_id"],
        requestTypeEnumId=request_type_enum_id,
        purposeEnumId=purpose_enum_id,
        routerEnumId=DEFAULT_GATEWAY_ROUTER_ENUM_ID,
        runServiceName=GATEWAY_RUN_SERVICE,
        brokerUri=gateway["rest_base_uri"],
        timeout=gateway["rest_timeout_seconds"],
        query=field_request_name,
        connectionName=connection_name,
        onlyChangedParameters="N",
        description=f"Moqui-side REST dispatch wrapper for gateway request {field_request_name}.",
    )


def append_atomic_component_parameters(
    root: ET.Element,
    root_device_id: str,
    device: dict,
    atomic_library: dict,
) -> set[str]:
    component_key = library_component_for_logical_model(device["logical_model"])
    component_meta = atomic_library["components"][component_key]
    control_method = default_control_method_for_device(device, atomic_library)
    overrides = {
        "PARENT_DEVICE_ID": root_device_id,
        component_meta["deviceIdVariable"]: device["device_id"],
        component_meta["nameVariable"]: device.get("physical_device_name", "") or device["device_id"],
        component_meta["deviceTypeVariable"]: device_type_for_logical_model(device["logical_model"]),
        component_meta["purposeVariable"]: "DepProcessControl",
        component_meta["descriptionVariable"]: device.get("notes", "") or f"Survey-derived {device['logical_model']} device.",
        component_meta["parameterCodePrefixVariable"]: device["device_id"],
    }
    control_variable = component_meta.get("controlMethodVariable")
    if control_variable:
        overrides[control_variable] = control_method

    fragment = compose_seed(component_meta, derive_defaults(component_key, component_meta, include_config=False, overrides=overrides), include_config=False)
    fragment_root = ET.fromstring(fragment)
    parameter_ids: set[str] = set()
    for child in fragment_root:
        if local_name(child.tag) in {"Device", "PhysicalDevice"}:
            continue
        root.append(child)
        if local_name(child.tag) == "Parameter":
            parameter_ids.add(child.attrib["parameterId"])
    return parameter_ids


def render_seed(model: dict, root_device_id: str) -> ET.Element:
    root = ET.Element("entity-facade-xml", {"type": "seed"})
    root.append(ET.Comment("Survey-derived draft seed. Review enums, request routing, and subsystem grouping before use."))
    atomic_library = load_catalog(ATOMIC_COMPONENT_LIBRARY_PATH)
    fsm_by_subsystem = append_statusflow_seed(root, model.get("fsm_model", {}))

    project_scope = model["project_scope"]
    group_ids = {row["group_device_id"] for row in model["device_groups"] if row["group_device_id"]}
    for group in model["device_groups"]:
        if not group["group_device_id"]:
            continue
        owner_subsystem = next((row for row in model["system_tree"]
            if subsystem_group_device_id(row["subsystem_id"]) == group["group_device_id"]), None)
        owner_fsm = fsm_by_subsystem.get(owner_subsystem["subsystem_id"]) if owner_subsystem else None
        initial_status_id = next((state["status_id"] for state in owner_fsm["states"] if state["initial"]), "") if owner_fsm else ""
        add_elem(root, "moqui.device.Device", deviceId=group["group_device_id"],
            parentDeviceId=group["parent_device_id"], deviceTypeEnumId=group["device_type_enum_id"],
            purposeEnumId=group["purpose_enum_id"], statusFlowId=owner_fsm["status_flow_id"] if owner_fsm else "",
            statusId=initial_status_id, description=group["notes"])
        add_elem(root, "moqui.device.DeviceGroup", deviceId=group["group_device_id"], groupName=group["group_name"])

    for controller in model["controllers"]:
        if not controller["controller_device_id"]:
            continue
        add_elem(root, "moqui.device.Device", deviceId=controller["controller_device_id"],
            parentDeviceId=controller["parent_device_id"], deviceTypeEnumId=controller["device_type_enum_id"],
            purposeEnumId="DepProcessControl", statusFlowId="DeviceBasicStatusFlow", statusId="DbsStandstill",
            description=controller["notes"] or f"{controller['controller_kind']} control runtime.")
        add_elem(root, "moqui.device.PhysicalDevice", deviceId=controller["controller_device_id"],
            deviceName=controller["controller_name"], softwareApplication=controller["application_id"] or controller["controller_kind"])

    for device in model["devices"]:
        control_method = default_control_method_for_device(device, atomic_library)
        add_elem(
            root,
            "moqui.device.Device",
            deviceId=device["device_id"],
            parentDeviceId=(subsystem_group_device_id(device["parent_subsystem_id"])
                            if subsystem_group_device_id(device["parent_subsystem_id"]) in group_ids else ""),
            deviceTypeEnumId=device_type_for_logical_model(device["logical_model"]),
            purposeEnumId="DepProcessControl",
            controlMethodEnumId=control_method,
            description=device.get("notes", "") or f"Survey-derived {device['logical_model']} device.",
        )
        add_elem(
            root,
            "moqui.device.PhysicalDevice",
            deviceId=device["device_id"],
            deviceName=device.get("physical_device_name", "") or device["device_id"],
        )

    for gateway in model.get("gateways", []):
        if not _gateway_row_is_meaningful(gateway):
            continue
        add_elem(
            root,
            "moqui.device.Device",
            deviceId=gateway["gateway_device_id"],
            deviceTypeEnumId=gateway.get("gateway_device_type_enum_id", "") or DEFAULT_GATEWAY_DEVICE_TYPE_ENUM_ID,
            purposeEnumId="DepProcessControl",
            description=gateway.get("notes", "") or "Survey-derived edge gateway.",
        )
        add_elem(
            root,
            "moqui.device.PhysicalDevice",
            deviceId=gateway["gateway_device_id"],
            deviceName=gateway["gateway_name"],
            softwareApplication="moqui-device-gateway",
        )

    for transport in model.get("gateway_transports", []):
        if not _gateway_transport_row_is_meaningful(transport) or transport["protocol"] != "opcua":
            continue
        target_controller_id = controller_for_domain(
            model, transport["scoped_domain_ids"][0] if transport["scoped_domain_ids"] else "", root_device_id
        )
        add_elem(
            root,
            "moqui.device.DeviceConnection",
            connectionName=transport["connection_name"],
            deviceId=target_controller_id,
            connectionTypeEnumId="DctDirectConnection",
            purposeEnumId="DcpOperations",
            driverEnumId=transport["driver_enum_id"] or "DcdOpcUa",
            transportEnumId=transport["transport_enum_id"] or "DctrTcp",
            transportConfig=transport["transport_config"],
            options=transport["options"],
            description=transport.get("notes", "") or f"Survey-derived OPC UA transport {transport['transport_id']}.",
        )

    for connection in model.get("plc4j_connections", []):
        if not _plc4j_connection_row_is_meaningful(connection):
            continue
        target_controller_id = controller_for_domain(
            model, connection["scoped_domain_ids"][0] if connection["scoped_domain_ids"] else "", root_device_id
        )
        add_elem(
            root,
            "moqui.device.DeviceConnection",
            connectionName=connection["connection_name"],
            deviceId=target_controller_id,
            driverEnumId=connection["driver_enum_id"],
            transportEnumId=connection["transport_enum_id"],
            transportConfig=connection["transport_config"],
            options=connection["options"],
            description=connection.get("notes", ""),
        )

    # Membership is a developer-approved engineering decision and is never inferred.
    for member in model["device_group_members"]:
        if not member["group_device_id"]:
            continue
        add_elem(root, "moqui.device.DeviceGroupMember", deviceId=member["group_device_id"],
            memberDeviceId=member["member_device_id"], purposeEnumId=member["purpose_enum_id"],
            sequenceNum=member["sequence_num"], description=member["notes"])

    existing_parameter_ids: set[str] = set()

    for device in model["devices"]:
        existing_parameter_ids.update(
            append_atomic_component_parameters(root, root_device_id, device, atomic_library)
        )

    for index, signal in enumerate(model["signals"], start=1):
        param_base = normalize_identifier(signal["signal_id"])
        parameter_def_id = f"PD_{param_base}"
        parameter_id = f"P_{param_base}"
        add_elem(
            root,
            "moqui.math.ParameterDef",
            parameterDefId=parameter_def_id,
            parameterTypeEnumId=parameter_type_for_signal(signal),
            purposeEnumId=purpose_for_signal(signal),
            parameterCode=f"SIG.{index:03d}",
            parameterName=title_case(signal["signal_name"]),
            description=signal.get("notes", "") or f"Survey-derived {signal['direction']} {signal['signal_kind']} signal from {signal['source_rule']}.",
        )
        add_elem(
            root,
                    "moqui.math.Parameter",
            parameterId=parameter_id,
            parameterDefId=parameter_def_id,
            deviceId=signal["device_id"],
            **default_value_attrs(parameter_type_for_signal(signal), signal["direction"]),
        )
        existing_parameter_ids.add(parameter_id)

    # DeviceConfig is atomic. Multi-device recipes are composed only by ordered rules.
    for config in model["device_configs"]:
        if not config["device_config_id"]:
            continue
        add_elem(root, "moqui.device.DeviceConfig", deviceConfigId=config["device_config_id"],
            parentConfigId=config["parent_config_id"], configTypeEnumId=config["config_type_enum_id"],
            purposeEnumId=config["purpose_enum_id"], deviceTypeEnumId=config["device_type_enum_id"],
            configName=config["config_name"], description=config["notes"],
            controlMethodEnumId=config["control_method_enum_id"], approximatedFunctionId=config["approximated_function_id"])
        for parameter in config["parameters"]:
            add_elem(root, "moqui.math.Parameter", parameterId=parameter["parameter_id"],
                deviceConfigId=config["device_config_id"], parameterDefId=parameter["parameter_def_id"],
                parameterAlias=parameter["parameter_alias"], sequenceNum=parameter["sequence_num"],
                numericValue=parameter["numeric_value"], symbolicValue=parameter["symbolic_value"],
                parameterEnumId=parameter["parameter_enum_id"])

    for rule_set in model["device_rule_sets"]:
        if not rule_set["device_rule_set_id"]:
            continue
        add_elem(root, "moqui.device.DeviceRuleSet", deviceRuleSetId=rule_set["device_rule_set_id"],
            parentRuleSetId=rule_set["parent_rule_set_id"], purposeEnumId=rule_set["purpose_enum_id"],
            deviceId=rule_set["root_device_id"], sequenceNum=rule_set["sequence_num"],
            ruleSetName=rule_set["rule_set_name"], description=rule_set["notes"])
        for rule in sorted(rule_set["rules"], key=lambda row: int(row["priority"])):
            add_elem(root, "moqui.device.DeviceRule", deviceRuleId=rule["device_rule_id"],
                parentRuleId=rule["parent_rule_id"], deviceRuleSetId=rule_set["device_rule_set_id"],
                deviceConfigId=rule["device_config_id"], deviceId=rule["target_device_id"],
                ruleTypeEnumId=rule["rule_type_enum_id"], ruleName=rule["rule_name"],
                priority=rule["priority"], serviceName=rule["service_name"],
                statusId=rule["status_id"], statusFlowId=rule["status_flow_id"],
                isEnabled="Y", runDevice="Y" if rule["run_device"] else "N", description=rule["notes"])

    signals_by_id = {signal["signal_id"]: signal for signal in model["signals"]}
    domain_rows = model["domains"] or []
    if not domain_rows:
        domain_rows = [
            {
                "domain_id": "DEFAULT",
                "domain_name": "Default",
                "natural_frequency_class": "unspecified",
                "scan_time": "T#100ms",
                "transport_scope": "",
                "devices": [],
                "signals": [signal["signal_id"] for signal in model["signals"]],
                "notes": "",
            }
        ]

    for domain in domain_rows:
        domain_id = normalize_identifier(domain["domain_id"])
        controller_device_id = domain.get("controller_device_id") or root_device_id
        polling_interval = parse_iec_time_to_ms(domain["scan_time"])
        domain_signals = [signals_by_id[signal_id] for signal_id in domain["signals"] if signal_id in signals_by_id]
        input_signals = [signal for signal in domain_signals if signal["direction"].lower() == "input"]
        output_signals = [signal for signal in domain_signals if signal["direction"].lower() == "output"]
        selected_transports = transports_for_domain(domain, model["transport_architecture"])
        transport_count = len(selected_transports)

        for transport_tag in selected_transports:
            router_enum_id = DEFAULT_GATEWAY_ROUTER_ENUM_ID if transport_tag == "gateway" else DEFAULT_PLC4J_ROUTER_ENUM_ID
            request_transport_suffix = title_case(transport_tag)
            connection = resolve_plc4j_connection_for_domain(domain, model) if transport_tag == "plc4j" else None
            gateway_transport = resolve_gateway_transport_for_domain(domain, model) if transport_tag == "gateway" else None

            if input_signals:
                request_name = request_name_for_transport(
                    f"{controller_device_id}_{domain_id}_InputsRead",
                    transport_tag,
                    transport_count,
                )
                request_attrs = {
                    "requestName": request_name,
                    "deviceId": controller_device_id,
                    "requestTypeEnumId": "DrtCyclic",
                    "purposeEnumId": "DrpMonitoring",
                    "routerEnumId": router_enum_id,
                    "pollingInterval": polling_interval,
                    "description": f"Survey-derived {request_transport_suffix.lower()} monitoring request for domain {domain['domain_name']}.",
                }
                if connection:
                    request_attrs["connectionName"] = connection["connection_name"]
                    request_attrs["runServiceName"] = (
                        model["transport_architecture"].get("default_run_service_name") or PLC4J_RUN_SERVICE
                    )
                if gateway_transport:
                    if gateway_transport["protocol"] == "mqtt":
                        request_attrs["brokerUri"] = gateway_transport["broker_uri"]
                    else:
                        request_attrs["connectionName"] = gateway_transport["connection_name"]
                add_elem(root, "moqui.device.DeviceRequest", **request_attrs)
                for sequence_num, signal in enumerate(input_signals, start=1):
                    add_elem(
                        root,
                        "moqui.device.DeviceRequestItem",
                        requestName=request_name,
                        parameterId=f"P_{normalize_identifier(signal['signal_id'])}",
                        sequenceNum=str(sequence_num),
                        requestItemName=signal["signal_name"],
                        query=signal["plc4j_query"] if transport_tag == "plc4j" else signal["gateway_query"],
                        itemTypeEnumId=request_item_type_for_signal(signal),
                    )
                if gateway_transport:
                    append_gateway_dispatch_wrapper(
                        root,
                        model,
                        request_name,
                        "DrtCyclic",
                        "DrpMonitoring",
                        gateway_transport,
                        gateway_transport["connection_name"] if gateway_transport["protocol"] == "opcua" else "",
                    )

            if output_signals:
                request_name = request_name_for_transport(
                    f"{controller_device_id}_{domain_id}_OutputsWrite",
                    transport_tag,
                    transport_count,
                )
                request_attrs = {
                    "requestName": request_name,
                    "deviceId": controller_device_id,
                    "requestTypeEnumId": "DrtWrite",
                    "purposeEnumId": "DrpControl",
                    "routerEnumId": router_enum_id,
                    "onlyChangedParameters": "Y",
                    "description": f"Survey-derived {request_transport_suffix.lower()} control request for domain {domain['domain_name']}.",
                }
                if connection:
                    request_attrs["connectionName"] = connection["connection_name"]
                    request_attrs["runServiceName"] = (
                        model["transport_architecture"].get("default_run_service_name") or PLC4J_RUN_SERVICE
                    )
                if gateway_transport:
                    if gateway_transport["protocol"] == "mqtt":
                        request_attrs["brokerUri"] = gateway_transport["broker_uri"]
                    else:
                        request_attrs["connectionName"] = gateway_transport["connection_name"]
                add_elem(root, "moqui.device.DeviceRequest", **request_attrs)
                for sequence_num, signal in enumerate(output_signals, start=1):
                    add_elem(
                        root,
                        "moqui.device.DeviceRequestItem",
                        requestName=request_name,
                        parameterId=f"P_{normalize_identifier(signal['signal_id'])}",
                        sequenceNum=str(sequence_num),
                        requestItemName=signal["signal_name"],
                        query=signal["plc4j_query"] if transport_tag == "plc4j" else signal["gateway_query"],
                        itemTypeEnumId=request_item_type_for_signal(signal),
                    )
                if gateway_transport:
                    append_gateway_dispatch_wrapper(
                        root,
                        model,
                        request_name,
                        "DrtWrite",
                        "DrpControl",
                        gateway_transport,
                        gateway_transport["connection_name"] if gateway_transport["protocol"] == "opcua" else "",
                    )

    log_transports = [
        row for row in model["gateway_transports"] if row.get("supports_plc_logs")
    ]
    if model["transport_architecture"]["gateway_required"] and log_transports:
        log_transport = log_transports[0]
        log_request_name = f"{root_device_id}_PlcLogSubscribe"
        add_elem(
            root,
            "moqui.device.DeviceRequest",
            requestName=log_request_name,
            deviceId=root_device_id,
            requestTypeEnumId="DrtSubscribe",
            purposeEnumId="DrpLogging",
            routerEnumId=DEFAULT_GATEWAY_ROUTER_ENUM_ID,
            brokerUri=log_transport["broker_uri"],
            query=log_transport["plc_log_topic"] or DEFAULT_LOG_TOPIC,
            description="Standard PLC LoggerFacade/LogDispatcher subscription; DeviceRequestItems are intentionally omitted.",
        )
        append_gateway_dispatch_wrapper(
            root, model, log_request_name, "DrtSubscribe", "DrpLogging", log_transport
        )

    live_rows = [row for row in model["live_parameters"] if any(row.values())]
    if live_rows and model["transport_architecture"]["gateway_required"]:
        live_transport = next(
            row for row in model["gateway_transports"] if row.get("supports_live_parameters")
        )
        parameter_devices = {
            elem.attrib["parameterId"]: elem.attrib.get("deviceId", "")
            for elem in root if isinstance(elem.tag, str) and local_name(elem.tag) == "Parameter"
        }
        rows_by_controller: dict[str, list[dict]] = {}
        for row in live_rows:
            if row["parameter_id"] not in parameter_devices:
                raise SystemExit(
                    f"Live-parameter whitelist selects unknown or non-device Parameter {row['parameter_id']}."
                )
            device_id = parameter_devices[row["parameter_id"]]
            controller_id = controller_for_device(model, device_id, root_device_id)
            rows_by_controller.setdefault(controller_id, []).append(row)
        for controller_id, controller_rows in sorted(rows_by_controller.items()):
            request_name = f"{controller_id}_LiveParametersWrite"
            add_elem(
                root,
                "moqui.device.DeviceRequest",
                requestName=request_name,
                deviceId=controller_id,
                requestTypeEnumId="DrtWrite",
                purposeEnumId="DrpControl",
                routerEnumId=DEFAULT_GATEWAY_ROUTER_ENUM_ID,
                brokerUri=live_transport["broker_uri"],
                onlyChangedParameters="Y",
                description="Approved live-parameter whitelist for MqttParameterSub and the generated JSON mapper.",
            )
            for sequence_num, row in enumerate(controller_rows, start=1):
                add_elem(root, "moqui.device.DeviceRequestItem", requestName=request_name,
                    parameterId=row["parameter_id"], sequenceNum=str(sequence_num),
                    requestItemName=row["mqtt_key"], query=live_transport["live_parameter_topic"])
            append_gateway_dispatch_wrapper(root, model, request_name, "DrtWrite", "DrpControl", live_transport)

    root.append(ET.Comment("Sampling-domain summary"))
    for domain in model["domains"]:
        root.append(
            ET.Comment(
                f"{domain['domain_id']}: {domain['domain_name']} | scan={domain['scan_time']} | devices={','.join(domain['devices'])} | signals={','.join(domain['signals'])}"
            )
        )
    return root


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a draft Moqui seed XML directly from upstream engineering surveys")
    parser.add_argument("--session-dir", type=Path, required=True, help="Saved session directory")
    parser.add_argument("--root-device-id", help="Optional explicit root Device ID")
    parser.add_argument("--output", type=Path, help="Optional output path")
    parser.add_argument("--output-name", help="Output file name when writing into the session seed-data directory")
    parser.add_argument("--draft", action="store_true", help="Render a review draft without approval gates")
    args = parser.parse_args()

    session_dir = args.session_dir.resolve()
    validate_upstream_surveys(session_dir)
    model = load_upstream_survey_model(session_dir)
    model["fsm_model"] = validate_fsm_surveys(session_dir, model)
    if not args.draft:
        required = ("device_model_approved", "device_groups_approved", "seed_generation_approved")
        missing = [name for name in required if not model["approvals"].get(name)]
        if missing:
            raise SystemExit("Final seed generation requires approvals: " + ", ".join(missing))
        if not model["approvals"].get("approved_by") or not model["approvals"].get("approved_at"):
            raise SystemExit("Final seed generation requires approved_by and approved_at provenance.")
    root_device_id = args.root_device_id or next(
        (row["controller_device_id"] for row in model["controllers"] if row["controller_device_id"]),
        infer_root_device_id(model, session_dir),
    )
    xml_root = render_seed(model, root_device_id)
    validate_generated_model_references(xml_root)
    validate_generated_enum_references(
        xml_root,
        load_enum_ids(
            [
                DEFAULT_MOQUI_DEVICE_DATA_PATH,
                DEFAULT_MOQUI_DEVICE_ENTITY_PATH,
                DEFAULT_MOQUI_MATH_ENTITY_PATH,
            ]
        ),
    )
    indent(xml_root)
    output_path = resolve_output_path(args)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(xml_root, encoding="unicode"),
        encoding="utf-8",
    )
    update_session_metadata(session_dir, output_path.resolve())
    print(f"Wrote survey-derived seed to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

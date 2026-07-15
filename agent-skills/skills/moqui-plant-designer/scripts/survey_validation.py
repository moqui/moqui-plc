from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ModuleNotFoundError as exc:
    raise SystemExit(
        "PyYAML is required to parse survey YAML files. Install it with "
        "`python3 -m pip install PyYAML`."
    ) from exc


ALLOWED_ACTUATION_FEEDBACK_CLASSES = {"DA-DF", "SA-DF", "SA-SAFD", "SA-SDFD", "SA-NO"}
SUPPORTED_LOGICAL_MODELS = {"Actuator", "ActuatorGroup", "ProcessPid", "Axis", "AxisGroup", "SignalMgmt"}
SUPPORTED_SIGNAL_DIRECTIONS = {"input", "output"}
SUPPORTED_IEC_TYPES = {"BOOL", "BYTE", "WORD", "DWORD", "LWORD", "INT", "UINT", "DINT", "UDINT", "REAL", "LREAL", "TIME", "STRING"}
SUPPORTED_TRANSPORT_MODES = {"gateway", "plc4j", "hybrid"}
SUPPORTED_DOMAIN_TRANSPORT_SCOPES = {"", "gateway", "plc4j", "both", "hybrid"}
SUPPORTED_GATEWAY_PROTOCOLS = {"mqtt", "opcua"}
SUPPORTED_FSM_COMPOSITIONS = {"flat", "nested"}
PLC4J_RUN_SERVICE = "moqui.plc4j.Plc4jServices.run#Plc4jRequest"


def _gateway_row_is_meaningful(row: dict) -> bool:
    return bool(
        row.get("gateway_device_id")
        or row.get("gateway_name")
        or row.get("scoped_subsystem_ids")
        or row.get("scoped_device_ids")
        or row.get("notes")
    )


def _gateway_transport_row_is_meaningful(row: dict) -> bool:
    return bool(
        row.get("transport_id")
        or row.get("gateway_device_id")
        or row.get("protocol")
        or row.get("broker_uri")
        or row.get("connection_name")
        or row.get("transport_config")
    )


def _plc4j_connection_row_is_meaningful(row: dict) -> bool:
    return bool(
        row.get("connection_name")
        or row.get("driver_enum_id")
        or row.get("transport_enum_id")
        or row.get("transport_config")
        or row.get("options")
        or row.get("scoped_domain_ids")
        or row.get("notes")
    )


def _normalize_transport_scope(value: str) -> str:
    lowered = value.strip().lower()
    if lowered == "hybrid":
        return "both"
    return lowered


def _read_session(session_dir: Path) -> tuple[Path, dict]:
    session_path = session_dir / "session.json"
    if not session_path.is_file():
        raise SystemExit(f"session.json not found in session directory: {session_dir}")
    return session_path, json.loads(session_path.read_text(encoding="utf-8"))


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _survey_path(session_dir: Path, filename: str) -> Path:
    return session_dir / "survey-answers" / filename


def _read_survey_text(session_dir: Path, filename: str, default_text: str = "") -> str:
    path = _survey_path(session_dir, filename)
    if not path.is_file():
        return default_text
    return path.read_text(encoding="utf-8")


def _load_yaml_document(session_dir: Path, filename: str, default_text: str = "") -> dict:
    raw_text = _read_survey_text(session_dir, filename, default_text)
    try:
        loaded = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        raise SystemExit(f"Invalid YAML in {filename}: {exc}") from exc
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise SystemExit(f"{filename} must contain a YAML mapping at the document root.")
    return loaded


def _as_str(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return value.strip()
    raise SystemExit(f"Expected scalar string-like value, got {type(value).__name__}.")


def _as_st(value: object) -> str:
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    return _as_str(value)


def _as_bool(value: object, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "y", "1"}:
            return True
        if lowered in {"false", "no", "n", "0"}:
            return False
    raise SystemExit(f"Expected boolean-compatible value, got {value!r}.")


def _as_list_of_dicts(document: dict, key: str, filename: str) -> list[dict]:
    value = document.get(key, [])
    if value is None:
        return []
    if not isinstance(value, list):
        raise SystemExit(f"{filename}: {key} must be a YAML list.")
    result: list[dict] = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            raise SystemExit(f"{filename}: {key}[{index}] must be a YAML mapping.")
        result.append(item)
    return result


def _as_list_of_strings(value: object, filename: str, field_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise SystemExit(f"{filename}: {field_name} must be a YAML list.")
    result: list[str] = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, (str, int, float)):
            raise SystemExit(
                f"{filename}: {field_name}[{index}] must be a scalar string-like value."
            )
        cleaned = _as_str(item)
        if cleaned:
            result.append(cleaned)
    return result


def _mapping(document: dict, key: str, filename: str) -> dict:
    value = document.get(key, {})
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise SystemExit(f"{filename}: {key} must be a YAML mapping.")
    return value


def _assignment_rows(value: object, filename: str, field_name: str) -> list[dict]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise SystemExit(f"{filename}: {field_name} must be a YAML list.")
    rows: list[dict] = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            raise SystemExit(f"{filename}: {field_name}[{index}] must be a YAML mapping.")
        rows.append(
            {
                "target": _as_str(item.get("target")),
                "expression": _as_st(item.get("expression")),
                "comment": _as_str(item.get("comment")),
            }
        )
    return rows


def load_upstream_survey_model(session_dir: Path) -> dict:
    _read_session(session_dir)

    decomposition_doc = _load_yaml_document(session_dir, "system-decomposition-survey.yaml")
    classification_doc = _load_yaml_document(session_dir, "elementary-device-classification-survey.yaml")
    signal_doc = _load_yaml_document(session_dir, "signal-catalog-survey.yaml")
    sampling_doc = _load_yaml_document(session_dir, "sampling-domains-survey.yaml")
    live_doc = _load_yaml_document(
        session_dir,
        "live-parameters-survey.yaml",
        "# Live parameters survey\nlive_parameters:\n",
    )
    gateway_doc = _load_yaml_document(
        session_dir,
        "gateway-topology-survey.yaml",
        "# Gateway topology survey\ngateways:\n",
    )
    transport_doc = _load_yaml_document(
        session_dir,
        "transport-architecture-survey.yaml",
        "# Transport architecture survey\ntransport_architecture:\n  primary_transport_mode: \"\"\n",
    )
    controller_doc = _load_yaml_document(session_dir, "controller-topology-survey.yaml")
    groups_doc = _load_yaml_document(session_dir, "device-groups-survey.yaml")
    config_doc = _load_yaml_document(session_dir, "device-config-survey.yaml")
    approval_doc = _load_yaml_document(session_dir, "approval-survey.yaml")

    controllers = []
    for block in _as_list_of_dicts(controller_doc, "controllers", "controller-topology-survey.yaml"):
        controllers.append({
            "controller_device_id": _as_str(block.get("controller_device_id")),
            "controller_name": _as_str(block.get("controller_name")),
            "controller_kind": _as_str(block.get("controller_kind")).lower(),
            "application_id": _as_str(block.get("application_id")),
            "device_type_enum_id": _as_str(block.get("device_type_enum_id")) or "DtPLC",
            "parent_device_id": _as_str(block.get("parent_device_id")),
            "notes": _as_str(block.get("notes")),
        })

    device_groups = []
    for block in _as_list_of_dicts(groups_doc, "device_groups", "device-groups-survey.yaml"):
        device_groups.append({
            "group_device_id": _as_str(block.get("group_device_id")),
            "group_name": _as_str(block.get("group_name")),
            "parent_device_id": _as_str(block.get("parent_device_id")),
            "device_type_enum_id": _as_str(block.get("device_type_enum_id")) or "DgtControl",
            "purpose_enum_id": _as_str(block.get("purpose_enum_id")) or "DepProcessControl",
            "notes": _as_str(block.get("notes")),
        })
    device_group_members = []
    for block in _as_list_of_dicts(groups_doc, "device_group_members", "device-groups-survey.yaml"):
        device_group_members.append({
            "group_device_id": _as_str(block.get("group_device_id")),
            "member_device_id": _as_str(block.get("member_device_id")),
            "purpose_enum_id": _as_str(block.get("purpose_enum_id")),
            "sequence_num": _as_str(block.get("sequence_num")) or "10",
            "notes": _as_str(block.get("notes")),
        })

    device_configs = []
    for block in _as_list_of_dicts(config_doc, "device_configs", "device-config-survey.yaml"):
        parameters = []
        for row in block.get("parameters") or []:
            if not isinstance(row, dict):
                raise SystemExit("device-config-survey.yaml: parameters entries must be mappings.")
            parameters.append({
                "parameter_id": _as_str(row.get("parameter_id")),
                "parameter_def_id": _as_str(row.get("parameter_def_id")),
                "parameter_alias": _as_str(row.get("parameter_alias")),
                "sequence_num": _as_str(row.get("sequence_num")) or "10",
                "numeric_value": _as_str(row.get("numeric_value")),
                "symbolic_value": _as_str(row.get("symbolic_value")),
                "parameter_enum_id": _as_str(row.get("parameter_enum_id")),
            })
        device_configs.append({
            "device_config_id": _as_str(block.get("device_config_id")),
            "parent_config_id": _as_str(block.get("parent_config_id")),
            "config_name": _as_str(block.get("config_name")),
            "config_type_enum_id": _as_str(block.get("config_type_enum_id")) or "DctApplyConfig",
            "purpose_enum_id": _as_str(block.get("purpose_enum_id")) or "DcpRunConfig",
            "device_type_enum_id": _as_str(block.get("device_type_enum_id")),
            "control_method_enum_id": _as_str(block.get("control_method_enum_id")),
            "approximated_function_id": _as_str(block.get("approximated_function_id")),
            "parameters": parameters,
            "notes": _as_str(block.get("notes")),
        })
    device_rule_sets = []
    for block in _as_list_of_dicts(config_doc, "device_rule_sets", "device-config-survey.yaml"):
        rules = []
        for row in block.get("rules") or []:
            if not isinstance(row, dict):
                raise SystemExit("device-config-survey.yaml: rules entries must be mappings.")
            rules.append({
                "device_rule_id": _as_str(row.get("device_rule_id")),
                "parent_rule_id": _as_str(row.get("parent_rule_id")),
                "device_config_id": _as_str(row.get("device_config_id")),
                "target_device_id": _as_str(row.get("target_device_id")),
                "rule_type_enum_id": _as_str(row.get("rule_type_enum_id")) or "DrtApplyConfig",
                "rule_name": _as_str(row.get("rule_name")),
                "priority": _as_str(row.get("priority")) or "10",
                "run_device": _as_bool(row.get("run_device"), default=False),
                "service_name": _as_str(row.get("service_name")),
                "status_id": _as_str(row.get("status_id")),
                "status_flow_id": _as_str(row.get("status_flow_id")),
                "notes": _as_str(row.get("notes")),
            })
        device_rule_sets.append({
            "device_rule_set_id": _as_str(block.get("device_rule_set_id")),
            "parent_rule_set_id": _as_str(block.get("parent_rule_set_id")),
            "root_device_id": _as_str(block.get("root_device_id")),
            "purpose_enum_id": _as_str(block.get("purpose_enum_id")) or "DrspConfiguration",
            "sequence_num": _as_str(block.get("sequence_num")) or "10",
            "rule_set_name": _as_str(block.get("rule_set_name")),
            "rules": rules,
            "notes": _as_str(block.get("notes")),
        })
    approval_map = _mapping(approval_doc, "approvals", "approval-survey.yaml")
    approvals = {
        "device_model_approved": _as_bool(approval_map.get("device_model_approved"), False),
        "device_groups_approved": _as_bool(approval_map.get("device_groups_approved"), False),
        "seed_generation_approved": _as_bool(approval_map.get("seed_generation_approved"), False),
        "hivemind_project_approved": _as_bool(approval_map.get("hivemind_project_approved"), False),
        "approved_by": _as_str(approval_map.get("approved_by")),
        "approved_at": _as_str(approval_map.get("approved_at")),
        "notes": _as_str(approval_map.get("notes")),
    }

    project_scope_map = _mapping(decomposition_doc, "project_scope", "system-decomposition-survey.yaml")
    project_scope = {
        "machine_name": _as_str(project_scope_map.get("machine_name")),
        "process_description": _as_str(project_scope_map.get("process_description")),
        "control_objective": _as_str(project_scope_map.get("control_objective")),
        "safety_scope": _as_str(project_scope_map.get("safety_scope")),
        "notes": _as_str(project_scope_map.get("notes")),
    }

    system_tree = []
    for block in _as_list_of_dicts(decomposition_doc, "system_tree", "system-decomposition-survey.yaml"):
        system_tree.append(
            {
                "subsystem_id": _as_str(block.get("subsystem_id")),
                "parent_subsystem_id": _as_str(block.get("parent_subsystem_id")),
                "subsystem_name": _as_str(block.get("subsystem_name")),
                "subsystem_type": _as_str(block.get("subsystem_type")),
                "control_responsibility": _as_str(block.get("control_responsibility")),
                "candidate_fsm": _as_str(block.get("candidate_fsm")),
                "notes": _as_str(block.get("notes")),
            }
        )

    devices = []
    for block in _as_list_of_dicts(
        classification_doc,
        "devices",
        "elementary-device-classification-survey.yaml",
    ):
        devices.append(
            {
                "device_id": _as_str(block.get("device_id")),
                "parent_subsystem_id": _as_str(block.get("parent_subsystem_id")),
                "physical_device_name": _as_str(block.get("physical_device_name")),
                "logical_model": _as_str(block.get("logical_model")),
                "actuation_feedback_class": _as_str(block.get("actuation_feedback_class")),
                "control_method_enum_id": _as_str(block.get("control_method_enum_id")),
                "positive_logic_required": _as_bool(block.get("positive_logic_required"), default=True),
                "expected_actuation_signals": _as_list_of_strings(
                    block.get("expected_actuation_signals"),
                    "elementary-device-classification-survey.yaml",
                    "expected_actuation_signals",
                ),
                "expected_feedback_signals": _as_list_of_strings(
                    block.get("expected_feedback_signals"),
                    "elementary-device-classification-survey.yaml",
                    "expected_feedback_signals",
                ),
                "notes": _as_str(block.get("notes")),
            }
        )

    naming_rules_block = _mapping(signal_doc, "naming_rules", "signal-catalog-survey.yaml")
    naming_rules = {
        "positive_logic_default": _as_bool(
            naming_rules_block.get("positive_logic_default"),
            default=True,
        ),
        "input_prefix": _as_str(naming_rules_block.get("input_prefix")),
        "output_prefix": _as_str(naming_rules_block.get("output_prefix")),
        "analog_suffix": _as_str(naming_rules_block.get("analog_suffix")),
        "digital_suffix": _as_str(naming_rules_block.get("digital_suffix")),
        "notes": _as_str(naming_rules_block.get("notes")),
    }

    signals = []
    for block in _as_list_of_dicts(signal_doc, "signals", "signal-catalog-survey.yaml"):
        signals.append(
            {
                "signal_id": _as_str(block.get("signal_id")),
                "device_id": _as_str(block.get("device_id")),
                "signal_name": _as_str(block.get("signal_name")),
                "direction": _as_str(block.get("direction")),
                "signal_kind": _as_str(block.get("signal_kind")),
                "iec_type": _as_str(block.get("iec_type")),
                "source_rule": _as_str(block.get("source_rule")),
                "gateway_query": _as_str(block.get("gateway_query")),
                "plc4j_query": _as_str(block.get("plc4j_query")),
                "reverse_logic": _as_bool(block.get("reverse_logic"), default=False),
                "notes": _as_str(block.get("notes")),
            }
        )

    domains = []
    for block in _as_list_of_dicts(sampling_doc, "domains", "sampling-domains-survey.yaml"):
        domains.append(
            {
                "domain_id": _as_str(block.get("domain_id")),
                "controller_device_id": _as_str(block.get("controller_device_id")),
                "domain_name": _as_str(block.get("domain_name")),
                "natural_frequency_class": _as_str(block.get("natural_frequency_class")),
                "scan_time": _as_str(block.get("scan_time")),
                "transport_scope": _as_str(block.get("transport_scope")),
                "transport_projection": _as_str(block.get("transport_projection")),
                "devices": _as_list_of_strings(
                    block.get("devices"),
                    "sampling-domains-survey.yaml",
                    "devices",
                ),
                "signals": _as_list_of_strings(
                    block.get("signals"),
                    "sampling-domains-survey.yaml",
                    "signals",
                ),
                "notes": _as_str(block.get("notes")),
            }
        )

    live_parameters = []
    for block in _as_list_of_dicts(live_doc, "live_parameters", "live-parameters-survey.yaml"):
        live_parameters.append(
            {
                "parameter_id": _as_str(block.get("parameter_id")),
                "device_id": _as_str(block.get("device_id")),
                "parameter_name": _as_str(block.get("parameter_name")),
                "iec_type": _as_str(block.get("iec_type")),
                "mqtt_key": _as_str(block.get("mqtt_key")),
                "notes": _as_str(block.get("notes")),
            }
        )

    gateways = []
    for block in _as_list_of_dicts(gateway_doc, "gateways", "gateway-topology-survey.yaml"):
        gateways.append(
            {
                "gateway_device_id": _as_str(block.get("gateway_device_id")),
                "gateway_name": _as_str(block.get("gateway_name")),
                "gateway_device_type_enum_id": _as_str(block.get("gateway_device_type_enum_id")),
                "gateway_member_purpose_enum_id": _as_str(block.get("gateway_member_purpose_enum_id")),
                "rest_base_uri": _as_str(block.get("rest_base_uri")),
                "rest_timeout_seconds": _as_str(block.get("rest_timeout_seconds")) or "30",
                "scoped_subsystem_ids": _as_list_of_strings(
                    block.get("scoped_subsystem_ids"),
                    "gateway-topology-survey.yaml",
                    "scoped_subsystem_ids",
                ),
                "scoped_device_ids": _as_list_of_strings(
                    block.get("scoped_device_ids"),
                    "gateway-topology-survey.yaml",
                    "scoped_device_ids",
                ),
                "notes": _as_str(block.get("notes")),
            }
        )

    transport_architecture_map = _mapping(
        transport_doc,
        "transport_architecture",
        "transport-architecture-survey.yaml",
    )
    gateway_projection_map = _mapping(
        transport_doc,
        "gateway_projection",
        "transport-architecture-survey.yaml",
    )
    plc4j_projection_map = _mapping(
        transport_doc,
        "plc4j_projection",
        "transport-architecture-survey.yaml",
    )

    transport_architecture = {
        "primary_transport_mode": _as_str(transport_architecture_map.get("primary_transport_mode")).lower(),
        "allows_hybrid_projection": _as_bool(transport_architecture_map.get("allows_hybrid_projection"), default=False),
        "notes": _as_str(transport_architecture_map.get("notes")),
        "gateway_required": _as_bool(gateway_projection_map.get("required"), default=False),
        "gateway_rationale": _as_str(gateway_projection_map.get("rationale")),
        "plc4j_required": _as_bool(plc4j_projection_map.get("required"), default=False),
        "default_run_service_name": _as_str(plc4j_projection_map.get("default_run_service_name")),
        "connection_strategy": _as_str(plc4j_projection_map.get("connection_strategy")),
        "plc4j_notes": _as_str(plc4j_projection_map.get("notes")),
    }

    gateway_transports = []
    for block in _as_list_of_dicts(
        transport_doc,
        "gateway_transports",
        "transport-architecture-survey.yaml",
    ):
        gateway_transports.append(
            {
                "transport_id": _as_str(block.get("transport_id")),
                "gateway_device_id": _as_str(block.get("gateway_device_id")),
                "protocol": _as_str(block.get("protocol")).lower(),
                "broker_uri": _as_str(block.get("broker_uri")),
                "connection_name": _as_str(block.get("connection_name")),
                "driver_enum_id": _as_str(block.get("driver_enum_id")),
                "transport_enum_id": _as_str(block.get("transport_enum_id")),
                "transport_config": _as_str(block.get("transport_config")),
                "options": _as_str(block.get("options")),
                "scoped_domain_ids": _as_list_of_strings(
                    block.get("scoped_domain_ids"),
                    "transport-architecture-survey.yaml",
                    "scoped_domain_ids",
                ),
                "plc_log_topic": _as_str(block.get("plc_log_topic")),
                "live_parameter_topic": _as_str(block.get("live_parameter_topic")),
                "supports_plc_logs": _as_bool(block.get("supports_plc_logs"), default=False),
                "supports_live_parameters": _as_bool(block.get("supports_live_parameters"), default=False),
                "notes": _as_str(block.get("notes")),
            }
        )

    plc4j_connections = []
    for block in _as_list_of_dicts(
        transport_doc,
        "plc4j_connections",
        "transport-architecture-survey.yaml",
    ):
        plc4j_connections.append(
            {
                "connection_name": _as_str(block.get("connection_name")),
                "driver_enum_id": _as_str(block.get("driver_enum_id")),
                "transport_enum_id": _as_str(block.get("transport_enum_id")),
                "transport_config": _as_str(block.get("transport_config")),
                "options": _as_str(block.get("options")),
                "scoped_domain_ids": _as_list_of_strings(
                    block.get("scoped_domain_ids"),
                    "transport-architecture-survey.yaml",
                    "scoped_domain_ids",
                ),
                "notes": _as_str(block.get("notes")),
            }
        )

    return {
        "machine_device_id": _as_str(controller_doc.get("machine_device_id")),
        "controllers": controllers,
        "device_groups": device_groups,
        "device_group_members": device_group_members,
        "device_configs": device_configs,
        "device_rule_sets": device_rule_sets,
        "approvals": approvals,
        "project_scope": project_scope,
        "system_tree": system_tree,
        "devices": devices,
        "naming_rules": naming_rules,
        "signals": signals,
        "domains": domains,
        "live_parameters": live_parameters,
        "gateways": gateways,
        "transport_architecture": transport_architecture,
        "gateway_transports": gateway_transports,
        "plc4j_connections": plc4j_connections,
    }


def load_fsm_survey_model(session_dir: Path) -> dict:
    """Load the optional PLC orchestration surveys without moving code semantics into Moqui."""
    fsm_doc = _load_yaml_document(session_dir, "main-fsm-survey.yaml", "fsms:\n")
    rule_doc = _load_yaml_document(session_dir, "main-rule-engine-survey.yaml", "fsms:\n")

    # Accept the original single-FSM draft so saved sessions remain readable.
    fsm_rows = _as_list_of_dicts(fsm_doc, "fsms", "main-fsm-survey.yaml")
    if not fsm_rows and _as_str(fsm_doc.get("status_flow_id")):
        fsm_rows = [fsm_doc]
    rule_rows = _as_list_of_dicts(rule_doc, "fsms", "main-rule-engine-survey.yaml")
    if not rule_rows and _as_str(rule_doc.get("status_flow_id")):
        rule_rows = [rule_doc]

    rules_by_key: dict[str, dict] = {}
    for row in rule_rows:
        key = _as_str(row.get("fsm_id")) or _as_str(row.get("status_flow_id"))
        if key:
            rules_by_key[key] = row

    fsms: list[dict] = []
    for row in fsm_rows:
        status_flow_id = _as_str(row.get("status_flow_id"))
        fsm_id = _as_str(row.get("fsm_id")) or status_flow_id
        raw_states = row.get("states") or []
        if not (fsm_id or status_flow_id or _as_str(row.get("owner_subsystem_id"))) and not any(
            isinstance(state, dict) and (_as_str(state.get("status_id")) or _as_str(state.get("status")))
            for state in raw_states
        ):
            continue
        rule_row = rules_by_key.get(fsm_id) or rules_by_key.get(status_flow_id) or {}
        states: list[dict] = []
        for index, state in enumerate(raw_states, start=1):
            if not isinstance(state, dict):
                raise SystemExit(f"main-fsm-survey.yaml: states[{index}] must be a YAML mapping.")
            status_id = _as_str(state.get("status_id")) or _as_str(state.get("status"))
            activate = state.get("activate") or {}
            deactivate = state.get("deactivate") or {}
            if not isinstance(activate, dict) or not isinstance(deactivate, dict):
                raise SystemExit("main-fsm-survey.yaml: activate and deactivate must be YAML mappings.")
            states.append(
                {
                    "status_id": status_id,
                    "name": _as_str(state.get("name")) or status_id,
                    "initial": _as_bool(state.get("initial"), default=index == 1),
                    "sequence": int(state.get("sequence", index) or index),
                    "activate": {
                        "device_groups": _as_list_of_strings(activate.get("device_groups"), "main-fsm-survey.yaml", "activate.device_groups"),
                        "physical_devices": _as_list_of_strings(activate.get("physical_devices"), "main-fsm-survey.yaml", "activate.physical_devices"),
                        "request_flags": _as_list_of_strings(activate.get("request_flags"), "main-fsm-survey.yaml", "activate.request_flags"),
                    },
                    "deactivate": {
                        "device_groups": _as_list_of_strings(deactivate.get("device_groups"), "main-fsm-survey.yaml", "deactivate.device_groups"),
                        "physical_devices": _as_list_of_strings(deactivate.get("physical_devices"), "main-fsm-survey.yaml", "deactivate.physical_devices"),
                        "request_flags": _as_list_of_strings(deactivate.get("request_flags"), "main-fsm-survey.yaml", "deactivate.request_flags"),
                    },
                    "output_assignments": _assignment_rows(
                        state.get("output_assignments"), "main-fsm-survey.yaml", "output_assignments"
                    ),
                    "outputs_reviewed": _as_bool(state.get("outputs_reviewed"), default=False),
                    "consume_transition_requests": _as_list_of_strings(
                        state.get("consume_transition_requests"), "main-fsm-survey.yaml", "consume_transition_requests"
                    ),
                    "notes": _as_str(state.get("notes")),
                }
            )
        transitions: list[dict] = []
        for index, transition in enumerate(rule_row.get("transitions") or [], start=1):
            if not isinstance(transition, dict):
                raise SystemExit(f"main-rule-engine-survey.yaml: transitions[{index}] must be a YAML mapping.")
            transitions.append(
                {
                    "from_status_id": _as_str(transition.get("from_status_id")) or _as_str(transition.get("from_status")),
                    "to_status_id": _as_str(transition.get("to_status_id")) or _as_str(transition.get("to_status")),
                    "to_fsm_id": _as_str(transition.get("to_fsm_id")),
                    "name": _as_str(transition.get("name")),
                    "condition": _as_st(transition.get("condition")),
                    "consume_condition": _as_st(transition.get("consume_condition")),
                    "request_assignments": _assignment_rows(
                        transition.get("request_assignments"),
                        "main-rule-engine-survey.yaml",
                        "request_assignments",
                    ),
                    "apply_assignments": _assignment_rows(
                        transition.get("apply_assignments"),
                        "main-rule-engine-survey.yaml",
                        "apply_assignments",
                    ),
                    "precedence": int(transition.get("precedence", index) or index),
                    "notes": _as_str(transition.get("notes")),
                }
            )
        predicates: list[dict] = []
        for index, predicate in enumerate(rule_row.get("predicates") or [], start=1):
            if isinstance(predicate, str):
                predicates.append({"name": predicate.strip(), "expression": "", "comment": ""})
            elif isinstance(predicate, dict):
                predicates.append(
                    {
                        "name": _as_str(predicate.get("name")),
                        "expression": _as_st(predicate.get("expression")),
                        "comment": _as_str(predicate.get("comment")),
                    }
                )
            else:
                raise SystemExit(f"main-rule-engine-survey.yaml: predicates[{index}] must be a string or mapping.")
        fsms.append(
            {
                "fsm_id": fsm_id,
                "owner_subsystem_id": _as_str(row.get("owner_subsystem_id")),
                "component_name": _as_str(row.get("component_name")) or fsm_id,
                "status_flow_id": status_flow_id,
                "status_type_id": _as_str(row.get("status_type_id")) or f"{status_flow_id}Type",
                "composition": (_as_str(row.get("composition")) or "flat").lower(),
                "parent_fsm_id": _as_str(row.get("parent_fsm_id")),
                "application_id": _as_str(row.get("application_id")),
                "call_sequence": int(row.get("call_sequence", len(fsms) + 1) or len(fsms) + 1),
                "enable_condition": _as_st(row.get("enable_condition")) or "TRUE",
                "completion_condition": _as_st(row.get("completion_condition")),
                "fault_status_id": _as_str(row.get("fault_status_id")),
                "code_generation_approved": _as_bool(row.get("code_generation_approved"), default=False),
                "states": states,
                "predicates": predicates,
                "transitions": transitions,
                "global_overrides": {
                    "fault_condition": _as_st((rule_row.get("global_overrides") or {}).get("fault_condition")),
                    "reset_condition": _as_st((rule_row.get("global_overrides") or {}).get("reset_condition")),
                    "notes": _as_str((rule_row.get("global_overrides") or {}).get("notes")),
                } if isinstance(rule_row.get("global_overrides") or {}, dict) else {},
                "notes": _as_str(row.get("notes")),
            }
        )
    return {"fsms": fsms}


def validate_fsm_surveys(session_dir: Path, upstream_model: dict | None = None) -> dict:
    """Validate FSM topology and traceability; conditions/actions remain code-owned review inputs."""
    model = load_fsm_survey_model(session_dir)
    fsms = model["fsms"]
    if not fsms:
        return model
    upstream_model = upstream_model or load_upstream_survey_model(session_dir)
    subsystem_ids = {row["subsystem_id"] for row in upstream_model["system_tree"]}
    device_ids = {row["device_id"] for row in upstream_model["devices"]}
    application_ids = {row["application_id"] for row in upstream_model["controllers"] if row["application_id"]}
    errors: list[str] = []
    fsm_ids: set[str] = set()
    flow_ids: set[str] = set()
    owner_ids: set[str] = set()
    for fsm in fsms:
        label = fsm["fsm_id"] or fsm["status_flow_id"] or "<unnamed>"
        if not fsm["fsm_id"] or not fsm["status_flow_id"] or not fsm["owner_subsystem_id"]:
            errors.append(f"FSM {label} must define fsm_id, status_flow_id, and owner_subsystem_id.")
        if fsm["fsm_id"] in fsm_ids:
            errors.append(f"Duplicate fsm_id {fsm['fsm_id']}.")
        if fsm["status_flow_id"] in flow_ids:
            errors.append(f"Duplicate status_flow_id {fsm['status_flow_id']}.")
        if fsm["owner_subsystem_id"] in owner_ids:
            errors.append(
                f"Subsystem {fsm['owner_subsystem_id']} owns multiple FSMs; create a child logical subsystem for each independently visible FSM."
            )
        fsm_ids.add(fsm["fsm_id"])
        flow_ids.add(fsm["status_flow_id"])
        owner_ids.add(fsm["owner_subsystem_id"])
        if fsm["owner_subsystem_id"] not in subsystem_ids:
            errors.append(f"FSM {label} references unknown owner_subsystem_id {fsm['owner_subsystem_id']}.")
        if fsm["application_id"] not in application_ids:
            errors.append(f"FSM {label} must reference an Application mapped to a PhysicalDevice in controller-topology-survey.yaml.")
        if fsm["composition"] not in SUPPORTED_FSM_COMPOSITIONS:
            errors.append(f"FSM {label} composition must be flat or nested.")
        state_ids = [state["status_id"] for state in fsm["states"]]
        if not state_ids or any(not value for value in state_ids):
            errors.append(f"FSM {label} must define non-empty status_id values.")
        if len(state_ids) != len(set(state_ids)):
            errors.append(f"FSM {label} contains duplicate status_id values.")
        if fsm["fault_status_id"] and fsm["fault_status_id"] not in state_ids:
            errors.append(f"FSM {label} references unknown fault_status_id {fsm['fault_status_id']}.")
        initial_count = sum(1 for state in fsm["states"] if state["initial"])
        if initial_count != 1:
            errors.append(f"FSM {label} must define exactly one initial state; found {initial_count}.")
        for state in fsm["states"]:
            for action_name in ("activate", "deactivate"):
                action = state[action_name]
                for subsystem_id in action["device_groups"]:
                    if subsystem_id not in subsystem_ids and subsystem_id not in device_ids:
                        errors.append(
                            f"FSM {label} state {state['status_id']} {action_name} references unknown device group {subsystem_id}."
                        )
                for device_id in action["physical_devices"]:
                    if device_id not in device_ids:
                        errors.append(
                            f"FSM {label} state {state['status_id']} {action_name} references unknown device {device_id}."
                        )
            for assignment in state["output_assignments"]:
                if not assignment["target"] or not assignment["expression"]:
                    errors.append(
                        f"FSM {label} state {state['status_id']} output assignments need target and expression."
                    )
        predicate_names: set[str] = set()
        for predicate in fsm["predicates"]:
            if not predicate["name"] or not predicate["expression"]:
                errors.append(f"FSM {label} predicates need name and expression.")
            if predicate["name"] in predicate_names:
                errors.append(f"FSM {label} contains duplicate predicate {predicate['name']}.")
            predicate_names.add(predicate["name"])
    by_id = {fsm["fsm_id"]: fsm for fsm in fsms}
    for fsm in fsms:
        label = fsm["fsm_id"]
        if fsm["parent_fsm_id"]:
            if fsm["composition"] != "nested":
                errors.append(f"FSM {label} has parent_fsm_id but composition is not nested.")
            if fsm["parent_fsm_id"] not in by_id:
                errors.append(f"FSM {label} references unknown parent_fsm_id {fsm['parent_fsm_id']}.")
            else:
                seen = {label}
                ancestor_id = fsm["parent_fsm_id"]
                while ancestor_id and ancestor_id in by_id:
                    if ancestor_id in seen:
                        errors.append(f"FSM parent cycle detected at {label}.")
                        break
                    seen.add(ancestor_id)
                    ancestor_id = by_id[ancestor_id]["parent_fsm_id"]
        source_states = {state["status_id"] for state in fsm["states"]}
        precedence_by_source: set[tuple[str, int]] = set()
        for transition in fsm["transitions"]:
            target_fsm = by_id.get(transition["to_fsm_id"] or label)
            if transition["from_status_id"] not in source_states:
                errors.append(f"FSM {label} transition starts from unknown state {transition['from_status_id']}.")
            if not target_fsm:
                errors.append(f"FSM {label} transition references unknown to_fsm_id {transition['to_fsm_id']}.")
            elif transition["to_status_id"] not in {state["status_id"] for state in target_fsm["states"]}:
                errors.append(f"FSM {label} transition points to unknown state {transition['to_status_id']} in {target_fsm['fsm_id']}.")
            elif target_fsm["fsm_id"] != label and not (
                target_fsm["parent_fsm_id"] == label or fsm["parent_fsm_id"] == target_fsm["fsm_id"]
            ):
                errors.append(
                    f"FSM {label} cross-flow transition may target only its direct parent or child flow, not {target_fsm['fsm_id']}."
                )
            if target_fsm and target_fsm["fsm_id"] != label and not transition["consume_condition"]:
                errors.append(
                    f"FSM {label} cross-flow transition {transition['from_status_id']} -> {transition['to_status_id']} needs consume_condition."
                )
            key = (transition["from_status_id"], transition["precedence"])
            if key in precedence_by_source:
                errors.append(f"FSM {label} has duplicate precedence {transition['precedence']} from {transition['from_status_id']}.")
            precedence_by_source.add(key)
            if not transition["condition"]:
                errors.append(f"FSM {label} transition {transition['from_status_id']} -> {transition['to_status_id']} needs a code-owned boolean condition.")
            for assignment in transition["request_assignments"]:
                if not assignment["target"] or not assignment["expression"]:
                    errors.append(
                        f"FSM {label} transition {transition['from_status_id']} -> {transition['to_status_id']} request assignments need target and expression."
                    )
            for assignment in transition["apply_assignments"]:
                if not assignment["target"] or not assignment["expression"]:
                    errors.append(
                        f"FSM {label} transition {transition['from_status_id']} -> {transition['to_status_id']} apply assignments need target and expression."
                    )
    if errors:
        raise SystemExit("FSM survey validation failed:\n- " + "\n- ".join(errors))
    return model


def validate_upstream_surveys(session_dir: Path) -> dict[str, list[str]]:
    session_path, session = _read_session(session_dir)
    model = load_upstream_survey_model(session_dir)

    errors: list[str] = []

    if not model["system_tree"]:
        errors.append("System decomposition survey must define at least one subsystem.")
    subsystem_ids: set[str] = set()
    for index, row in enumerate(model["system_tree"], start=1):
        subsystem_id = row["subsystem_id"]
        subsystem_name = row["subsystem_name"]
        subsystem_type = row["subsystem_type"]
        if not subsystem_id or not subsystem_name or not subsystem_type:
            errors.append(
                f"System decomposition subsystem #{index} must define subsystem_id, subsystem_name, and subsystem_type."
            )
            continue
        subsystem_ids.add(subsystem_id)

    meaningful_controllers = [row for row in model["controllers"] if row["controller_device_id"] or row["controller_name"]]
    if not meaningful_controllers:
        errors.append("Controller topology must define at least one hardware CPU or CODESYS Application.")
    controller_ids: set[str] = set()
    application_ids: set[str] = set()
    for index, row in enumerate(meaningful_controllers, start=1):
        controller_id = row["controller_device_id"]
        if not controller_id or not row["controller_name"] or row["controller_kind"] not in {"hardware_cpu", "codesys_application"}:
            errors.append(
                f"Controller topology entry #{index} must define controller_device_id, controller_name, and controller_kind as hardware_cpu or codesys_application."
            )
        if controller_id in controller_ids:
            errors.append(f"Duplicate controller_device_id {controller_id}.")
        controller_ids.add(controller_id)
        if row["controller_kind"] == "codesys_application" and not row["application_id"]:
            errors.append(f"CODESYS controller {controller_id} must define application_id.")
        if row["application_id"]:
            if row["application_id"] in application_ids:
                errors.append(f"Duplicate application_id {row['application_id']} in controller topology.")
            application_ids.add(row["application_id"])

    if not model["devices"]:
        errors.append("Elementary device classification survey must define at least one device.")
    device_ids: set[str] = set()
    for index, row in enumerate(model["devices"], start=1):
        device_id = row["device_id"]
        parent_subsystem_id = row["parent_subsystem_id"]
        logical_model = row["logical_model"]
        feedback_class = row["actuation_feedback_class"]
        actuation_signals = row["expected_actuation_signals"]
        feedback_signals = row["expected_feedback_signals"]
        if not device_id or not parent_subsystem_id or not logical_model or not feedback_class:
            errors.append(
                f"Elementary device classification #{index} must define device_id, parent_subsystem_id, logical_model, and actuation_feedback_class."
            )
            continue
        if parent_subsystem_id not in subsystem_ids:
            errors.append(
                f"Elementary device {device_id} references unknown parent_subsystem_id {parent_subsystem_id}."
            )
        if feedback_class not in ALLOWED_ACTUATION_FEEDBACK_CLASSES:
            errors.append(
                f"Elementary device {device_id} uses unsupported actuation_feedback_class {feedback_class}."
            )
        if logical_model not in SUPPORTED_LOGICAL_MODELS:
            errors.append(
                f"Elementary device {device_id} uses unsupported logical_model {logical_model}."
            )
        if not actuation_signals and not feedback_signals:
            errors.append(
                f"Elementary device {device_id} must declare expected_actuation_signals or expected_feedback_signals."
            )
        device_ids.add(device_id)

    group_ids: set[str] = set()
    meaningful_groups = [row for row in model["device_groups"] if row["group_device_id"] or row["group_name"]]
    if not meaningful_groups:
        errors.append("Device group survey must explicitly define at least one DeviceGroup.")
    for index, row in enumerate(meaningful_groups, start=1):
        if not row["group_device_id"] or not row["group_name"]:
            errors.append(f"Device group entry #{index} must define group_device_id and group_name.")
        if row["group_device_id"] in group_ids:
            errors.append(f"Duplicate group_device_id {row['group_device_id']}.")
        group_ids.add(row["group_device_id"])
    if model["machine_device_id"] not in group_ids:
        errors.append("controller-topology-survey.yaml machine_device_id must reference an explicit DeviceGroup.")
    for row in meaningful_groups:
        if row["parent_device_id"] and row["parent_device_id"] not in group_ids:
            errors.append(f"DeviceGroup {row['group_device_id']} references unknown parent group {row['parent_device_id']}.")
    for row in meaningful_controllers:
        if row["parent_device_id"] not in group_ids:
            errors.append(f"Controller {row['controller_device_id']} must reference an explicit parent DeviceGroup.")

    known_device_ids = device_ids | controller_ids | group_ids | {
        row["gateway_device_id"] for row in model["gateways"] if row["gateway_device_id"]
    }
    membership: dict[str, set[str]] = {group_id: set() for group_id in group_ids}
    meaningful_members = [row for row in model["device_group_members"] if row["group_device_id"] or row["member_device_id"]]
    for index, row in enumerate(meaningful_members, start=1):
        if row["group_device_id"] not in group_ids:
            errors.append(f"DeviceGroupMember #{index} references unknown group {row['group_device_id']}.")
        if row["member_device_id"] not in known_device_ids:
            errors.append(f"DeviceGroupMember #{index} references unknown member {row['member_device_id']}.")
        if not row["purpose_enum_id"]:
            errors.append(f"DeviceGroupMember #{index} must define purpose_enum_id.")
        membership.setdefault(row["group_device_id"], set()).add(row["member_device_id"])
    member_roles = {(row["member_device_id"], row["purpose_enum_id"]) for row in meaningful_members}
    for device_id in device_ids:
        if not any(member_id == device_id for member_id, _ in member_roles):
            errors.append(f"Elementary Device {device_id} must belong to an explicit DeviceGroup.")
    for controller_id in controller_ids:
        if (controller_id, "DgmpProcessPLC") not in member_roles:
            errors.append(f"Controller {controller_id} must have an explicit DgmpProcessPLC membership.")
    for gateway in (row for row in model["gateways"] if row["gateway_device_id"]):
        if (gateway["gateway_device_id"], gateway["gateway_member_purpose_enum_id"] or "DgmpEdgeGateway") not in member_roles:
            errors.append(f"Gateway {gateway['gateway_device_id']} must have an explicit gateway-role membership.")

    config_ids: set[str] = set()
    parameter_ids: set[str] = set()
    for index, config in enumerate(row for row in model["device_configs"] if row["device_config_id"] or row["config_name"]):
        if not config["device_config_id"] or not config["config_name"] or not config["device_type_enum_id"]:
            errors.append(f"DeviceConfig #{index + 1} must define device_config_id, config_name, and device_type_enum_id.")
        if config["device_config_id"] in config_ids:
            errors.append(f"Duplicate device_config_id {config['device_config_id']}.")
        config_ids.add(config["device_config_id"])
        for parameter in config["parameters"]:
            if not parameter["parameter_id"] or not parameter["parameter_def_id"]:
                errors.append(f"DeviceConfig {config['device_config_id']} parameters need parameter_id and parameter_def_id.")
            if parameter["parameter_id"] in parameter_ids:
                errors.append(f"Duplicate configuration parameter_id {parameter['parameter_id']}.")
            parameter_ids.add(parameter["parameter_id"])
            values = [parameter["numeric_value"], parameter["symbolic_value"], parameter["parameter_enum_id"]]
            if sum(bool(value) for value in values) != 1:
                errors.append(f"Configuration parameter {parameter['parameter_id']} must define exactly one value field.")

    def group_scope(root_id: str) -> set[str]:
        result = {root_id}
        pending = [root_id]
        while pending:
            current = pending.pop()
            for member in membership.get(current, set()):
                if member not in result:
                    result.add(member)
                    if member in group_ids:
                        pending.append(member)
        return result

    rule_set_ids: set[str] = set()
    for index, rule_set in enumerate(row for row in model["device_rule_sets"] if row["device_rule_set_id"] or row["rule_set_name"]):
        root_id = rule_set["root_device_id"]
        if not rule_set["device_rule_set_id"] or not root_id or not rule_set["rule_set_name"]:
            errors.append(f"DeviceRuleSet #{index + 1} must define device_rule_set_id, root_device_id, and rule_set_name.")
        if root_id not in known_device_ids:
            errors.append(f"DeviceRuleSet {rule_set['device_rule_set_id']} references unknown root_device_id {root_id}.")
        if rule_set["device_rule_set_id"] in rule_set_ids:
            errors.append(f"Duplicate device_rule_set_id {rule_set['device_rule_set_id']}.")
        rule_set_ids.add(rule_set["device_rule_set_id"])
        scope = group_scope(root_id) if root_id in group_ids else {root_id}
        priorities: set[int] = set()
        for rule in rule_set["rules"]:
            if not rule["device_rule_id"] or not rule["rule_name"] or rule["device_config_id"] not in config_ids:
                errors.append(f"Rules in {rule_set['device_rule_set_id']} need device_rule_id, rule_name, and a known device_config_id.")
            if rule["target_device_id"] not in scope:
                errors.append(f"DeviceRule {rule['device_rule_id']} target {rule['target_device_id']} is outside root scope {root_id}.")
            try:
                priority = int(rule["priority"])
                if priority in priorities:
                    errors.append(f"DeviceRuleSet {rule_set['device_rule_set_id']} has duplicate priority {priority}.")
                priorities.add(priority)
            except ValueError:
                errors.append(f"DeviceRule {rule['device_rule_id']} priority must be an integer.")

    if not model["signals"]:
        errors.append("Signal catalog survey must define at least one signal.")
    signal_ids: set[str] = set()
    for index, row in enumerate(model["signals"], start=1):
        signal_id = row["signal_id"]
        device_id = row["device_id"]
        signal_name = row["signal_name"]
        direction = row["direction"]
        signal_kind = row["signal_kind"]
        iec_type = row["iec_type"]
        source_rule = row["source_rule"]
        if not signal_id or not device_id or not signal_name or not direction or not signal_kind or not iec_type or not source_rule:
            errors.append(
                f"Signal catalog entry #{index} must define signal_id, device_id, signal_name, direction, signal_kind, iec_type, and source_rule."
            )
            continue
        if device_id not in device_ids:
            errors.append(f"Signal {signal_id} references unknown device_id {device_id}.")
        if direction.lower() not in SUPPORTED_SIGNAL_DIRECTIONS:
            errors.append(f"Signal {signal_id} uses unsupported direction {direction}.")
        if iec_type.upper() not in SUPPORTED_IEC_TYPES:
            errors.append(f"Signal {signal_id} uses unsupported iec_type {iec_type}.")
        signal_ids.add(signal_id)

    if not model["domains"]:
        errors.append("Sampling domains survey must define at least one domain.")
    for index, row in enumerate(model["domains"], start=1):
        domain_id = row["domain_id"]
        domain_name = row["domain_name"]
        natural_frequency_class = row["natural_frequency_class"]
        scan_time = row["scan_time"]
        devices = row["devices"]
        signals = row["signals"]
        if not domain_id or not domain_name or not natural_frequency_class or not scan_time:
            errors.append(
                f"Sampling domain #{index} must define domain_id, domain_name, natural_frequency_class, and scan_time."
            )
            continue
        if row["controller_device_id"] not in controller_ids:
            errors.append(f"Sampling domain {domain_id} must reference a known controller_device_id.")
        if not devices and not signals:
            errors.append(f"Sampling domain {domain_id} must reference at least one device or signal.")
        for device_id in devices:
            if device_id not in device_ids:
                errors.append(f"Sampling domain {domain_id} references unknown device_id {device_id}.")
        for signal_id in signals:
            if signal_id not in signal_ids:
                errors.append(f"Sampling domain {domain_id} references unknown signal_id {signal_id}.")

    for index, row in enumerate(model["live_parameters"], start=1):
        if not any(row.values()):
            continue
        parameter_id = row["parameter_id"]
        device_id = row["device_id"]
        parameter_name = row["parameter_name"]
        iec_type = row["iec_type"]
        mqtt_key = row["mqtt_key"]
        if not parameter_id or not device_id or not parameter_name or not iec_type or not mqtt_key:
            errors.append(
                f"Live-parameter entry #{index} must define parameter_id, device_id, parameter_name, iec_type, and mqtt_key."
            )
            continue
        if device_id not in device_ids:
            errors.append(f"Live-parameter {parameter_id} references unknown device_id {device_id}.")
        if iec_type.upper() not in SUPPORTED_IEC_TYPES:
            errors.append(f"Live-parameter {parameter_id} uses unsupported iec_type {iec_type}.")

    for index, row in enumerate(model["gateways"], start=1):
        if not _gateway_row_is_meaningful(row):
            continue
        gateway_device_id = row["gateway_device_id"]
        gateway_name = row["gateway_name"]
        scoped_subsystem_ids = row["scoped_subsystem_ids"]
        scoped_device_ids = row["scoped_device_ids"]
        if not gateway_device_id or not gateway_name:
            errors.append(
                f"Gateway topology entry #{index} must define gateway_device_id and gateway_name."
            )
            continue
        if not scoped_subsystem_ids and not scoped_device_ids:
            errors.append(
                f"Gateway topology entry {gateway_device_id} must reference scoped_subsystem_ids or scoped_device_ids."
            )
        for subsystem_id in scoped_subsystem_ids:
            if subsystem_id not in subsystem_ids:
                errors.append(
                    f"Gateway topology {gateway_device_id} references unknown scoped_subsystem_id {subsystem_id}."
                )
        for device_id in scoped_device_ids:
            if device_id not in device_ids:
                errors.append(
                    f"Gateway topology {gateway_device_id} references unknown scoped_device_id {device_id}."
                )

    transport = model["transport_architecture"]
    primary_transport_mode = transport["primary_transport_mode"]
    if primary_transport_mode not in SUPPORTED_TRANSPORT_MODES:
        errors.append(
            "Transport architecture must define primary_transport_mode as gateway, plc4j, or hybrid."
        )
    if primary_transport_mode == "gateway" and not transport["gateway_required"]:
        errors.append("Transport architecture mode gateway requires gateway_projection.required = true.")
    if primary_transport_mode == "plc4j" and not transport["plc4j_required"]:
        errors.append("Transport architecture mode plc4j requires plc4j_projection.required = true.")
    if primary_transport_mode == "hybrid":
        if not transport["allows_hybrid_projection"]:
            errors.append("Transport architecture mode hybrid requires allows_hybrid_projection = true.")
        if not (transport["gateway_required"] and transport["plc4j_required"]):
            errors.append("Transport architecture mode hybrid requires both gateway and plc4j projections.")
    if not (transport["gateway_required"] or transport["plc4j_required"]):
        errors.append("Transport architecture must require at least one projection: gateway or plc4j.")
    if transport["plc4j_required"] and transport["default_run_service_name"] != PLC4J_RUN_SERVICE:
        errors.append(
            f"PLC4J projection must use default_run_service_name {PLC4J_RUN_SERVICE}."
        )
    meaningful_gateways = [row for row in model["gateways"] if _gateway_row_is_meaningful(row)]
    if transport["gateway_required"] and not meaningful_gateways:
        errors.append("Gateway projection is required, but gateway-topology-survey.yaml does not define any gateway.")

    gateway_ids = {row["gateway_device_id"] for row in meaningful_gateways}
    for gateway in meaningful_gateways:
        if not gateway["rest_base_uri"]:
            errors.append(f"Gateway topology {gateway['gateway_device_id']} must define rest_base_uri.")
        if not gateway["rest_timeout_seconds"].isdigit() or int(gateway["rest_timeout_seconds"]) <= 0:
            errors.append(
                f"Gateway topology {gateway['gateway_device_id']} rest_timeout_seconds must be a positive integer."
            )

    meaningful_gateway_transports = [
        row for row in model["gateway_transports"] if _gateway_transport_row_is_meaningful(row)
    ]
    if transport["gateway_required"] and not meaningful_gateway_transports:
        errors.append(
            "Gateway projection is required, but transport-architecture-survey.yaml does not define any gateway_transports."
        )
    domain_ids = {row["domain_id"] for row in model["domains"]}
    for index, row in enumerate(model["gateway_transports"], start=1):
        if not _gateway_transport_row_is_meaningful(row):
            continue
        label = row["transport_id"] or f"#{index}"
        if not row["transport_id"] or not row["gateway_device_id"] or not row["protocol"]:
            errors.append(f"Gateway transport {label} must define transport_id, gateway_device_id, and protocol.")
            continue
        if row["gateway_device_id"] not in gateway_ids:
            errors.append(f"Gateway transport {label} references unknown gateway_device_id {row['gateway_device_id']}.")
        if not row["scoped_domain_ids"] and not row["supports_plc_logs"] and not row["supports_live_parameters"]:
            errors.append(
                f"Gateway transport {label} must scope at least one sampling domain or support a declared PLC log/live-parameter channel."
            )
        if row["protocol"] not in SUPPORTED_GATEWAY_PROTOCOLS:
            errors.append(f"Gateway transport {label} uses unsupported protocol {row['protocol']}.")
        if row["protocol"] == "mqtt" and not row["broker_uri"]:
            errors.append(f"MQTT gateway transport {label} must define broker_uri.")
        if row["protocol"] == "opcua":
            if not row["connection_name"] or not row["transport_config"]:
                errors.append(f"OPC UA gateway transport {label} must define connection_name and transport_config.")
            if row["driver_enum_id"] and row["driver_enum_id"] != "DcdOpcUa":
                errors.append(f"OPC UA gateway transport {label} must use driver_enum_id DcdOpcUa.")
        if row["supports_plc_logs"] and (row["protocol"] != "mqtt" or not row["plc_log_topic"]):
            errors.append(
                f"Gateway transport {label} with supports_plc_logs must be MQTT and define plc_log_topic."
            )
        if row["supports_live_parameters"] and (
            row["protocol"] != "mqtt" or not row["live_parameter_topic"]
        ):
            errors.append(
                f"Gateway transport {label} with supports_live_parameters must be MQTT and define live_parameter_topic."
            )
        for domain_id in row["scoped_domain_ids"]:
            if domain_id not in domain_ids:
                errors.append(f"Gateway transport {label} references unknown scoped_domain_id {domain_id}.")

    if transport["gateway_required"]:
        for domain in model["domains"]:
            scope = _normalize_transport_scope(domain["transport_projection"])
            if primary_transport_mode == "gateway" or scope in {"gateway", "both"}:
                matches = [
                    row for row in meaningful_gateway_transports
                    if domain["domain_id"] in row["scoped_domain_ids"]
                ]
                if len(matches) != 1:
                    errors.append(
                        f"Gateway-scoped sampling domain {domain['domain_id']} must resolve to exactly one gateway_transport; found {len(matches)}."
                    )

    live_transport_count = sum(1 for row in meaningful_gateway_transports if row["supports_live_parameters"])
    log_transport_count = sum(1 for row in meaningful_gateway_transports if row["supports_plc_logs"])
    if any(any(row.values()) for row in model["live_parameters"]) and live_transport_count != 1:
        errors.append(
            f"Live parameters require exactly one gateway_transport with supports_live_parameters = true; found {live_transport_count}."
        )
    if log_transport_count > 1:
        errors.append(
            f"At most one gateway_transport may define supports_plc_logs = true; found {log_transport_count}."
        )

    meaningful_plc4j_connections = [
        row for row in model["plc4j_connections"] if _plc4j_connection_row_is_meaningful(row)
    ]
    if transport["plc4j_required"] and not meaningful_plc4j_connections:
        errors.append(
            "PLC4J projection is required, but transport-architecture-survey.yaml does not define any plc4j_connections."
        )

    for index, row in enumerate(model["plc4j_connections"], start=1):
        if not _plc4j_connection_row_is_meaningful(row):
            continue
        connection_name = row["connection_name"]
        driver_enum_id = row["driver_enum_id"]
        transport_enum_id = row["transport_enum_id"]
        transport_config = row["transport_config"]
        scoped_domain_ids = row["scoped_domain_ids"]
        if not connection_name or not driver_enum_id or not transport_config:
            errors.append(
                f"PLC4J connection #{index} must define connection_name, driver_enum_id, and transport_config."
            )
        if driver_enum_id != "DcdSimulated" and not transport_enum_id:
            errors.append(
                f"PLC4J connection {connection_name or f'#{index}'} must define transport_enum_id unless driver_enum_id is DcdSimulated."
            )
        for domain_id in scoped_domain_ids:
            if domain_id not in {row["domain_id"] for row in model["domains"]}:
                errors.append(
                    f"PLC4J connection {connection_name or f'#{index}'} references unknown scoped_domain_id {domain_id}."
                )

    for row in model["domains"]:
        scope = _normalize_transport_scope(row["transport_projection"])
        domain_id = row["domain_id"]
        if scope not in SUPPORTED_DOMAIN_TRANSPORT_SCOPES:
            errors.append(
                f"Sampling domain {domain_id} uses unsupported transport_projection {row['transport_projection']}."
            )
            continue
        if primary_transport_mode == "gateway" and scope in {"plc4j", "both"}:
            errors.append(
                f"Sampling domain {domain_id} cannot require plc4j transport when primary_transport_mode is gateway."
            )
        if primary_transport_mode == "plc4j" and scope in {"gateway", "both"}:
            errors.append(
                f"Sampling domain {domain_id} cannot require gateway transport when primary_transport_mode is plc4j."
            )
        if primary_transport_mode == "gateway" or scope in {"gateway", "both"}:
            for signal_id in row["signals"]:
                signal_row = next((signal for signal in model["signals"] if signal["signal_id"] == signal_id), None)
                if signal_row and not signal_row["gateway_query"]:
                    errors.append(
                        f"Signal {signal_id} belongs to gateway-scoped domain {domain_id} but does not define gateway_query."
                    )
        if primary_transport_mode == "hybrid" and scope not in {"gateway", "plc4j", "both"}:
            errors.append(
                f"Sampling domain {domain_id} must define transport_scope as gateway, plc4j, or both when primary_transport_mode is hybrid."
            )

        if primary_transport_mode == "plc4j" or scope in {"plc4j", "both"}:
            matching_connections = [
                connection
                for connection in meaningful_plc4j_connections
                if not connection["scoped_domain_ids"] or domain_id in connection["scoped_domain_ids"]
            ]
            if not matching_connections:
                errors.append(
                    f"Sampling domain {domain_id} requires plc4j transport but no matching plc4j_connection covers it."
                )
            for signal_id in row["signals"]:
                signal_row = next((signal for signal in model["signals"] if signal["signal_id"] == signal_id), None)
                if signal_row and not signal_row["plc4j_query"]:
                    errors.append(
                        f"Signal {signal_id} belongs to plc4j-scoped domain {domain_id} but does not define plc4j_query."
                    )

    if any(any(row.values()) for row in model["live_parameters"]) and not transport["gateway_required"]:
        errors.append(
            "Live parameters currently project through MQTT/MqttParameterSub, so gateway_projection.required must be true when live_parameters are defined."
        )

    if errors:
        raise SystemExit("Upstream engineering survey validation failed:\n- " + "\n- ".join(errors))

    steps = session.setdefault("steps", {})
    for step_name, note in (
        ("system_decomposition", "Validated system decomposition survey."),
        ("device_classification", "Validated elementary device classification survey."),
        ("signal_catalog", "Validated signal catalog survey."),
        ("sampling_design", "Validated sampling domains survey."),
    ):
        step = steps.setdefault(step_name, {"status": "pending", "notes": ""})
        step["status"] = "reviewed"
        step["notes"] = note
    session["updatedAt"] = _utc_now()
    session_path.write_text(json.dumps(session, indent=2) + "\n", encoding="utf-8")

    return {
        "subsystemIds": sorted(subsystem_ids),
        "deviceIds": sorted(device_ids),
        "signalIds": sorted(signal_ids),
        "liveParameterIds": sorted(
            [row["parameter_id"] for row in model["live_parameters"] if row.get("parameter_id")]
        ),
        "validatedSurveys": [
            "system-decomposition-survey.yaml",
            "elementary-device-classification-survey.yaml",
            "signal-catalog-survey.yaml",
            "sampling-domains-survey.yaml",
            "live-parameters-survey.yaml",
            "gateway-topology-survey.yaml",
            "transport-architecture-survey.yaml",
        ],
    }

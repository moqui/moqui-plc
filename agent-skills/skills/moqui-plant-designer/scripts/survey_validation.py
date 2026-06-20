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
PLC4J_RUN_SERVICE = "moqui.plc4j.Plc4jServices.run#Plc4jRequest"


def _gateway_row_is_meaningful(row: dict) -> bool:
    return bool(
        row.get("gateway_device_id")
        or row.get("gateway_name")
        or row.get("scoped_subsystem_ids")
        or row.get("scoped_device_ids")
        or row.get("notes")
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
        "project_scope": project_scope,
        "system_tree": system_tree,
        "devices": devices,
        "naming_rules": naming_rules,
        "signals": signals,
        "domains": domains,
        "live_parameters": live_parameters,
        "gateways": gateways,
        "transport_architecture": transport_architecture,
        "plc4j_connections": plc4j_connections,
    }


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

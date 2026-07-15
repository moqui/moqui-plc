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
from datetime import datetime, timezone
from pathlib import Path


DIRS = [
    "survey-answers",
    "seed-data",
    "generated-plc",
    "generated-recipes",
    "generated-config",
    "attachments",
    "notes",
    "exports",
]


STANDARD_SURVEY_FILES = {
    "controller-topology-survey.yaml": """# One PhysicalDevice per hardware CPU or CODESYS Application.
machine_device_id: ""
controllers:
  - controller_device_id: ""
    controller_name: ""
    controller_kind: ""
    application_id: ""
    device_type_enum_id: "DtPLC"
    parent_device_id: ""
    notes: ""
""",
    "device-groups-survey.yaml": """# Explicit group model decided by the PLC developer; no groups are inferred.
device_groups:
  - group_device_id: ""
    group_name: ""
    parent_device_id: ""
    device_type_enum_id: "DgtControl"
    purpose_enum_id: "DepProcessControl"
    notes: ""
device_group_members:
  - group_device_id: ""
    member_device_id: ""
    purpose_enum_id: ""
    sequence_num: 10
    notes: ""
""",
    "device-config-survey.yaml": """# Atomic configurations composed by ordered DeviceRuleSet/DeviceRule rows.
device_configs:
  - device_config_id: ""
    parent_config_id: ""
    config_name: ""
    config_type_enum_id: "DctApplyConfig"
    purpose_enum_id: "DcpRunConfig"
    device_type_enum_id: ""
    control_method_enum_id: ""
    approximated_function_id: ""
    parameters:
      - parameter_id: ""
        parameter_def_id: ""
        parameter_alias: ""
        sequence_num: 10
        numeric_value: ""
        symbolic_value: ""
        parameter_enum_id: ""
    notes: ""
device_rule_sets:
  - device_rule_set_id: ""
    parent_rule_set_id: ""
    root_device_id: ""
    purpose_enum_id: "DrspConfiguration"
    sequence_num: 10
    rule_set_name: ""
    rules:
      - device_rule_id: ""
        parent_rule_id: ""
        device_config_id: ""
        target_device_id: ""
        rule_type_enum_id: "DrtApplyConfig"
        rule_name: ""
        priority: 10
        run_device: false
        service_name: ""
        status_id: ""
        status_flow_id: ""
        notes: ""
    notes: ""
""",
    "approval-survey.yaml": """# Human approval provenance. Final artifacts are blocked until approved.
approvals:
  device_model_approved: false
  device_groups_approved: false
  seed_generation_approved: false
  hivemind_project_approved: false
  approved_by: ""
  approved_at: ""
  notes: ""
""",
    "system-decomposition-survey.yaml": """# System decomposition survey
project_scope:
  machine_name: ""
  process_description: ""
  control_objective: ""
  safety_scope: ""
  notes: ""
system_tree:
  - subsystem_id: ""
    parent_subsystem_id: ""
    subsystem_name: ""
    subsystem_type: ""
    control_responsibility: ""
    candidate_fsm: ""
    notes: ""
""",
    "elementary-device-classification-survey.yaml": """# Elementary device classification survey
devices:
  - device_id: ""
    parent_subsystem_id: ""
    physical_device_name: ""
    logical_model: ""
    actuation_feedback_class: ""
    control_method_enum_id: ""
    positive_logic_required: true
    expected_actuation_signals: []
    expected_feedback_signals: []
    notes: ""
""",
    "signal-catalog-survey.yaml": """# Signal catalog survey
naming_rules:
  positive_logic_default: true
  input_prefix: ""
  output_prefix: ""
  analog_suffix: ""
  digital_suffix: ""
  notes: ""
signals:
  - signal_id: ""
    device_id: ""
    signal_name: ""
    direction: ""
    signal_kind: ""
    iec_type: ""
    source_rule: ""
    gateway_query: ""
    plc4j_query: ""
    reverse_logic: false
    notes: ""
""",
    "sampling-domains-survey.yaml": """# Sampling domains survey
domains:
  - domain_id: ""
    controller_device_id: ""
    domain_name: ""
    natural_frequency_class: ""
    scan_time: ""
    transport_scope: ""
    transport_projection: ""
    devices: []
    signals: []
    notes: ""
""",
    "live-parameters-survey.yaml": """# Live parameters survey
live_parameters:
  - parameter_id: ""
    device_id: ""
    parameter_name: ""
    iec_type: ""
    mqtt_key: ""
    notes: ""
""",
    "gateway-topology-survey.yaml": """# Gateway topology survey
gateways:
  - gateway_device_id: ""
    gateway_name: ""
    gateway_device_type_enum_id: "DtEdgeGateway"
    gateway_member_purpose_enum_id: "DgmpEdgeGateway"
    rest_base_uri: ""
    rest_timeout_seconds: 30
    scoped_subsystem_ids: []
    scoped_device_ids: []
    notes: ""
""",
    "transport-architecture-survey.yaml": """# Transport architecture survey
transport_architecture:
  primary_transport_mode: ""
  allows_hybrid_projection: false
  notes: ""
gateway_projection:
  required: false
  rationale: ""
gateway_transports:
  - transport_id: ""
    gateway_device_id: ""
    protocol: ""
    broker_uri: ""
    connection_name: ""
    driver_enum_id: ""
    transport_enum_id: ""
    transport_config: ""
    options: ""
    scoped_domain_ids: []
    supports_plc_logs: false
    plc_log_topic: ""
    supports_live_parameters: false
    live_parameter_topic: ""
    notes: ""
plc4j_projection:
  required: false
  default_run_service_name: "moqui.plc4j.Plc4jServices.run#Plc4jRequest"
  connection_strategy: ""
  notes: ""
plc4j_connections:
  - connection_name: ""
    driver_enum_id: ""
    transport_enum_id: ""
    transport_config: ""
    options: ""
    scoped_domain_ids: []
    notes: ""
""",
    "main-fsm-survey.yaml": """# PLC FSM topology and state-output survey. Flat FSMs are the default.
fsms:
  - fsm_id: ""
    owner_subsystem_id: ""
    component_name: ""
    status_flow_id: ""
    status_type_id: ""
    composition: flat
    parent_fsm_id: ""
    application_id: ""
    call_sequence: 0
    enable_condition: "TRUE"
    completion_condition: ""
    fault_status_id: ""
    code_generation_approved: false
    states:
      - status_id: ""
        name: ""
        initial: true
        sequence: 1
        activate:
          device_groups: []
          physical_devices: []
          request_flags: []
        deactivate:
          device_groups: []
          physical_devices: []
          request_flags: []
        consume_transition_requests: []
        output_assignments: []
        outputs_reviewed: false
        notes: ""
    notes: ""
""",
    "main-rule-engine-survey.yaml": """# Code-owned predicates and transition policy; never persisted as executable DB expressions.
fsms:
  - fsm_id: ""
    status_flow_id: ""
    predicates: []
    transitions:
      - from_status_id: ""
        to_status_id: ""
        to_fsm_id: ""
        name: ""
        condition: ""
        consume_condition: ""
        request_assignments: []
        apply_assignments: []
        precedence: 1
        notes: ""
    global_overrides:
      fault_condition: ""
      reset_condition: ""
      notes: ""
""",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_session(session_id: str, project_name: str, customer_name: str) -> dict:
    now = utc_now()
    return {
        "sessionId": session_id,
        "projectName": project_name,
        "customerName": customer_name,
        "createdAt": now,
        "updatedAt": now,
        "status": "in_progress",
        "currentStage": "system_decomposition",
        "currentSkill": "moqui-plant-designer",
        "workflowOrder": [
            "moqui-device-seed-designer",
            "moqui-plc-designer",
            "moqui-device-config-designer",
            "moqui-plc-config",
        ],
        "paths": {
            "surveyAnswersDir": "survey-answers",
            "seedDataDir": "seed-data",
            "generatedPlcDir": "generated-plc",
            "generatedRecipesDir": "generated-recipes",
            "generatedConfigDir": "generated-config",
            "attachmentsDir": "attachments",
            "notesDir": "notes",
            "exportsDir": "exports",
        },
        "artifacts": {
            "seedData": [],
            "generatedPlc": [],
            "generatedRecipes": [],
            "generatedConfig": [],
            "attachments": [],
            "surveys": [
                "survey-answers/system-decomposition-survey.yaml",
                "survey-answers/controller-topology-survey.yaml",
                "survey-answers/device-groups-survey.yaml",
                "survey-answers/device-config-survey.yaml",
                "survey-answers/approval-survey.yaml",
                "survey-answers/elementary-device-classification-survey.yaml",
                "survey-answers/signal-catalog-survey.yaml",
                "survey-answers/sampling-domains-survey.yaml",
                "survey-answers/live-parameters-survey.yaml",
                "survey-answers/gateway-topology-survey.yaml",
                "survey-answers/transport-architecture-survey.yaml",
                "survey-answers/main-fsm-survey.yaml",
                "survey-answers/main-rule-engine-survey.yaml",
            ],
        },
        "steps": {
            "system_decomposition": {"status": "pending", "notes": ""},
            "device_classification": {"status": "pending", "notes": ""},
            "signal_catalog": {"status": "pending", "notes": ""},
            "sampling_design": {"status": "pending", "notes": ""},
            "seed_design": {"status": "pending", "notes": ""},
            "plc_design": {"status": "pending", "notes": ""},
            "config_recipe": {"status": "pending", "notes": ""},
            "plc_framework_config": {"status": "pending", "notes": ""},
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize a saved Moqui plant-design session")
    parser.add_argument("session_id", help="Stable session identifier")
    parser.add_argument("--project-name", default="", help="Human-readable project name")
    parser.add_argument("--customer-name", default="", help="Human-readable customer name")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[3] / "output" / "sessions",
        help="Base directory that will contain the session folder",
    )
    args = parser.parse_args()

    session_dir = args.root / args.session_id
    session_path = session_dir / "session.json"
    if session_path.exists():
        print(f"Session already exists: {session_path}")
        return 0

    session_dir.mkdir(parents=True, exist_ok=True)
    for name in DIRS:
        (session_dir / name).mkdir(parents=True, exist_ok=True)
    survey_dir = session_dir / "survey-answers"
    for filename, content in STANDARD_SURVEY_FILES.items():
        survey_path = survey_dir / filename
        if not survey_path.exists():
            survey_path.write_text(content, encoding="utf-8")

    session = build_session(
        session_id=args.session_id,
        project_name=args.project_name or args.session_id,
        customer_name=args.customer_name,
    )
    session_path.write_text(json.dumps(session, indent=2) + "\n", encoding="utf-8")
    print(f"Initialized session at {session_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"
PYTHON = sys.executable


def run_ok(*args: str) -> str:
    result = subprocess.run(
        args,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"Command failed ({result.returncode}): {' '.join(args)}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return result.stdout


def run_fail(*args: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode == 0:
        raise AssertionError(f"Command unexpectedly succeeded: {' '.join(args)}")
    return result


class SkillRegressionTest(unittest.TestCase):
    maxDiff = None

    def init_session_from_fixture(self, fixture_name: str) -> Path:
        tmp_root = Path(tempfile.mkdtemp(prefix="agent-skills-tests-"))
        session_id = fixture_name
        run_ok(
            PYTHON,
            "skills/moqui-plant-designer/scripts/init_session.py",
            session_id,
            "--root",
            str(tmp_root),
        )
        session_dir = tmp_root / session_id
        fixture_survey_dir = FIXTURES_DIR / fixture_name / "survey-answers"
        target_survey_dir = session_dir / "survey-answers"
        for fixture_file in fixture_survey_dir.glob("*.yaml"):
            shutil.copy2(fixture_file, target_survey_dir / fixture_file.name)
        self.addCleanup(lambda: shutil.rmtree(tmp_root, ignore_errors=True))
        return session_dir

    def init_blank_session(self, session_id: str = "blank-session") -> Path:
        tmp_root = Path(tempfile.mkdtemp(prefix="agent-skills-tests-"))
        run_ok(
            PYTHON,
            "skills/moqui-plant-designer/scripts/init_session.py",
            session_id,
            "--root",
            str(tmp_root),
        )
        self.addCleanup(lambda: shutil.rmtree(tmp_root, ignore_errors=True))
        return tmp_root / session_id

    def test_gateway_valid_fixture_end_to_end(self) -> None:
        session_dir = self.init_session_from_fixture("gateway-valid")

        validate_out = run_ok(
            PYTHON,
            "skills/moqui-plant-designer/scripts/validate_upstream_surveys.py",
            str(session_dir),
        )
        self.assertIn("Upstream engineering surveys validated.", validate_out)

        run_ok(
            PYTHON,
            "skills/moqui-device-seed-designer/scripts/render_seed_from_surveys.py",
            "--session-dir",
            str(session_dir),
        )
        transport_out = run_ok(
            PYTHON,
            "skills/moqui-device-seed-designer/scripts/validate_transport_projection.py",
            "--session-dir",
            str(session_dir),
        )
        self.assertIn("Transport projection validated.", transport_out)
        run_ok(
            PYTHON,
            "skills/moqui-device-gateway-startup/scripts/render_gateway_startup_guide.py",
            "--session-dir",
            str(session_dir),
        )

        seed_path = session_dir / "seed-data" / "survey-derived-seed.xml"
        guide_path = session_dir / "generated-config" / "gateway-startup-guide.md"
        self.assertTrue(seed_path.is_file())
        self.assertTrue(guide_path.is_file())

        seed_text = seed_path.read_text(encoding="utf-8")
        guide_text = guide_path.read_text(encoding="utf-8")
        self.assertIn('deviceTypeEnumId="DtEdgeGateway"', seed_text)
        self.assertIn('purposeEnumId="DgmpProcessPLC"', seed_text)
        self.assertIn('parameterDefId="PD_LAMP_01_ENABLE_REQUEST"', seed_text)
        self.assertIn('parameterId="P_LAMP_01_ENABLE_REQUEST"', seed_text)
        self.assertIn('parameterDefId="PD_LAMP_01_ENABLE_TIME"', seed_text)
        self.assertIn('brokerUri="paho-mqtt5:?brokerUrl=tcp://artemis:1883&amp;qos=1"', seed_text)
        self.assertIn('query="moqui/uv-line/lamp01/cmd"', seed_text)
        self.assertIn('requestName="UV_LINE_PLC_FAST_OutputsWrite_GatewayDispatch"', seed_text)
        self.assertIn('runServiceName="moqui.device.DeviceGatewayServices.run#GatewayDeviceRequest"', seed_text)
        self.assertIn('brokerUri="http://gateway-edge-01:8081"', seed_text)
        self.assertIn('query="UV_LINE_PLC_FAST_OutputsWrite"', seed_text)
        self.assertIn('query="moqui-plc"', seed_text)
        self.assertIn('query="moqui/parameters/live"', seed_text)
        self.assertIn("UV_LINE_PLC_FAST_OutputsWrite", guide_text)
        self.assertIn("GW_EDGE_01", guide_text)
        self.assertIn("PLC log request", guide_text)
        self.assertIn("Moqui REST dispatch wrappers", guide_text)
        self.assertNotIn("OutputsWrite_GatewayDispatch` is routed", guide_text)

    def test_gateway_opcua_domain_generates_connection_and_rest_wrapper(self) -> None:
        session_dir = self.init_session_from_fixture("gateway-valid")
        transport_path = session_dir / "survey-answers" / "transport-architecture-survey.yaml"
        transport_path.write_text(
            """transport_architecture:
  primary_transport_mode: gateway
  allows_hybrid_projection: false
  notes: OPC UA process transport with MQTT operational channels.
gateway_projection:
  required: true
  rationale: Gateway owns OPC UA polling and writes.
gateway_transports:
  - transport_id: OPCUA_PLC
    gateway_device_id: GW_EDGE_01
    protocol: opcua
    connection_name: UvLineOpcUa
    driver_enum_id: DcdOpcUa
    transport_enum_id: DctrTcp
    transport_config: plc-uv-line:4840/moqui
    options: securityPolicy=None
    scoped_domain_ids: [FAST]
    supports_plc_logs: false
    supports_live_parameters: false
  - transport_id: MQTT_OPERATIONS
    gateway_device_id: GW_EDGE_01
    protocol: mqtt
    broker_uri: paho-mqtt5:?brokerUrl=tcp://artemis:1883&qos=1
    scoped_domain_ids: []
    supports_plc_logs: true
    plc_log_topic: moqui-plc
    supports_live_parameters: true
    live_parameter_topic: moqui/parameters/live
plc4j_projection:
  required: false
  default_run_service_name: moqui.plc4j.Plc4jServices.run#Plc4jRequest
  connection_strategy: ""
  notes: ""
""",
            encoding="utf-8",
        )
        signal_path = session_dir / "survey-answers" / "signal-catalog-survey.yaml"
        signal_path.write_text(
            signal_path.read_text(encoding="utf-8").replace(
                "gateway_query: moqui/uv-line/lamp01/cmd",
                "gateway_query: ns=2;s=UvLine.Lamp01.Cmd",
            ),
            encoding="utf-8",
        )

        run_ok(
            PYTHON,
            "skills/moqui-device-seed-designer/scripts/render_seed_from_surveys.py",
            "--session-dir",
            str(session_dir),
        )
        run_ok(
            PYTHON,
            "skills/moqui-device-seed-designer/scripts/validate_transport_projection.py",
            "--session-dir",
            str(session_dir),
        )
        seed_text = (session_dir / "seed-data" / "survey-derived-seed.xml").read_text(encoding="utf-8")
        self.assertIn('connectionName="UvLineOpcUa"', seed_text)
        self.assertIn('driverEnumId="DcdOpcUa"', seed_text)
        self.assertIn('transportConfig="plc-uv-line:4840/moqui"', seed_text)
        self.assertIn('requestName="UV_LINE_PLC_FAST_OutputsWrite"', seed_text)
        self.assertIn('query="ns=2;s=UvLine.Lamp01.Cmd"', seed_text)
        self.assertIn('requestName="UV_LINE_PLC_FAST_OutputsWrite_GatewayDispatch"', seed_text)
        self.assertIn('brokerUri="http://gateway-edge-01:8081"', seed_text)

    def test_multi_subsystem_fixture_end_to_end(self) -> None:
        session_dir = self.init_session_from_fixture("multi-subsystem-valid")

        run_ok(
            PYTHON,
            "skills/moqui-plant-designer/scripts/validate_upstream_surveys.py",
            str(session_dir),
        )
        run_ok(
            PYTHON,
            "skills/moqui-device-seed-designer/scripts/render_seed_from_surveys.py",
            "--session-dir",
            str(session_dir),
        )
        run_ok(
            PYTHON,
            "skills/moqui-device-gateway-startup/scripts/render_gateway_startup_guide.py",
            "--session-dir",
            str(session_dir),
        )

        seed_text = (session_dir / "seed-data" / "survey-derived-seed.xml").read_text(encoding="utf-8")
        guide_text = (session_dir / "generated-config" / "gateway-startup-guide.md").read_text(encoding="utf-8")

        self.assertIn('deviceId="DG_SS_TRANSPORT"', seed_text)
        self.assertIn('deviceId="DG_SS_CURE"', seed_text)
        self.assertIn('statusFlowId="TransportStatusFlow" statusId="TrStopped"', seed_text)
        self.assertIn('statusFlowId="CureStatusFlow" statusId="CuStandby"', seed_text)
        self.assertIn('toStatusFlowId="TransportStatusFlow"', seed_text)
        self.assertNotIn("conditionExpression=", seed_text)
        self.assertIn('memberDeviceId="CONVEYOR_MOTOR"', seed_text)
        self.assertIn('memberDeviceId="UV_LAMP_BANK"', seed_text)
        self.assertIn('parameterDefId="PD_CONVEYOR_MOTOR_ENABLE_REQUEST"', seed_text)
        self.assertIn('parameterDefId="PD_UV_LAMP_BANK_ACTUATOR_GROUP_ID"', seed_text)
        self.assertIn('parameterDefId="PD_UV_LAMP_BANK_AUTOCHANGE_LEVEL"', seed_text)
        self.assertIn('requestName="CURE_CELL_PLC_FAST_CTRL_OutputsWrite"', seed_text)
        self.assertIn('requestName="CURE_CELL_PLC_FAST_FB_InputsRead"', seed_text)
        self.assertIn("GW_EDGE_CURE_01", guide_text)
        self.assertIn("CONVEYOR_MOTOR", guide_text)
        self.assertIn("UV_LAMP_BANK", guide_text)
        self.assertIn("CURE_CELL_PLC_FAST_CTRL_OutputsWrite", guide_text)
        self.assertIn("CURE_CELL_PLC_FAST_FB_InputsRead", guide_text)

        framework_fixture = session_dir / "attachments" / "framework-fixture"
        (framework_fixture / "src" / "main").mkdir(parents=True, exist_ok=True)
        (framework_fixture / "src" / "main" / "FrameworkMarker.st").write_text("TYPE FrameworkMarker : BOOL; END_TYPE\n", encoding="utf-8")
        run_ok(
            PYTHON,
            "skills/moqui-plc-designer/scripts/render_codesys_applications.py",
            "--session-dir",
            str(session_dir),
            "--framework-source",
            str(framework_fixture),
        )
        applications_root = session_dir / "generated-plc" / "codesys-applications"
        project_manifest = json.loads((applications_root / "codesys-project-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(
            {row["applicationId"] for row in project_manifest["applications"]},
            {"TransportApplication", "CureApplication"},
        )
        cure_component = applications_root / "CureApplication" / "runtime" / "component" / "cure"
        cure_main = (cure_component / "src" / "main" / "mantle" / "cure" / "Main.pou").read_text(encoding="utf-8")
        cure_controller = (cure_component / "src" / "main" / "mantle" / "cure" / "CureLampController.pou").read_text(encoding="utf-8")
        cure_facade = (cure_component / "src" / "main" / "org" / "moqui" / "device" / "DeviceFacade.dut").read_text(encoding="utf-8")
        cure_manifest = json.loads((applications_root / "CureApplication" / "application-manifest.json").read_text(encoding="utf-8"))
        self.assertIn("dev.uvLampBankGroupEnable := TRUE;", cure_main)
        self.assertIn("(* No fault state defined for this FSM. *)", cure_main)
        self.assertNotIn("IF dev.faultRequest THEN dev.status := MainStatus.Curing", cure_main)
        self.assertIn("dev.cureLampStatus := CureLampStatus.Active;", cure_controller)
        self.assertIn("uvLampBank : ActuatorGroup;", cure_facade)
        self.assertNotIn("${", cure_main + cure_controller + cure_facade)
        self.assertEqual([row["callSequence"] for row in cure_manifest["fsmInvocationOrder"]], [0, 10, 20])
        self.assertTrue((applications_root / "CureApplication" / "plc-traceability.md").is_file())
        self.assertTrue((applications_root / "CureApplication" / "framework" / "src" / "main" / "FrameworkMarker.st").is_file())
        self.assertLess(cure_main.index("cureLampController("), cure_main.index("cureMonitorController("))
        generated_sources = list((applications_root / "CureApplication").glob("**/*.pou")) + list(
            (applications_root / "CureApplication").glob("**/*.dut")
        )
        for generated_source in generated_sources:
            generated_text = generated_source.read_text(encoding="utf-8")
            self.assertNotIn("${", generated_text, generated_source)
            self.assertNotIn("__COND_", generated_text, generated_source)

        run_ok(
            PYTHON,
            "skills/moqui-plc-designer/scripts/render_statusflow_templates.py",
            str(session_dir / "seed-data" / "survey-derived-seed.xml"),
            "TransportStatusFlow",
            "--session-dir",
            str(session_dir),
            "--component-name",
            "transport",
        )
        component_dir = session_dir / "generated-plc" / "transport" / "src" / "main" / "mantle" / "transport"
        main_text = (component_dir / "Main.pou").read_text(encoding="utf-8")
        rule_text = (component_dir / "MainRuleEngine.pou").read_text(encoding="utf-8")
        self.assertIn("IF dev.runningRequest THEN", main_text)
        self.assertNotIn("__COND_STOPPED_TO_RUNNING__", main_text)
        self.assertIn("IF dev.startTransportAllowed THEN", rule_text)
        self.assertIn("dev.runningRequest := TRUE;", rule_text)

        run_ok(
            PYTHON,
            "skills/moqui-plant-designer/scripts/render_engineering_dossier.py",
            "--session-dir",
            str(session_dir),
            "--work-effort-id",
            "PLC_CURE_CELL",
        )
        dossier_text = (session_dir / "notes" / "engineering-specification.md").read_text(encoding="utf-8")
        wiki_seed = (session_dir / "seed-data" / "engineering-wiki-seed.xml").read_text(encoding="utf-8")
        self.assertIn("TransportFsm", dossier_text)
        self.assertIn("Prove FAT/SAT", dossier_text)
        self.assertIn('workEffortId="PLC_CURE_CELL"', wiki_seed)

    def test_plc4j_valid_fixture_end_to_end(self) -> None:
        session_dir = self.init_session_from_fixture("plc4j-valid")

        run_ok(
            PYTHON,
            "skills/moqui-plant-designer/scripts/validate_upstream_surveys.py",
            str(session_dir),
        )
        run_ok(
            PYTHON,
            "skills/moqui-device-seed-designer/scripts/render_seed_from_surveys.py",
            "--session-dir",
            str(session_dir),
        )
        projection_out = run_ok(
            PYTHON,
            "skills/moqui-device-seed-designer/scripts/validate_transport_projection.py",
            "--session-dir",
            str(session_dir),
        )

        seed_text = (session_dir / "seed-data" / "survey-derived-seed.xml").read_text(encoding="utf-8")
        self.assertIn('connectionName="ModbusUvConnection"', seed_text)
        self.assertIn('driverEnumId="DcdModbusTCP"', seed_text)
        self.assertIn('transportEnumId="DctrTcp"', seed_text)
        self.assertIn('routerEnumId="DrrDirect"', seed_text)
        self.assertIn('runServiceName="moqui.plc4j.Plc4jServices.run#Plc4jRequest"', seed_text)
        self.assertIn('query="coil:1:BOOL"', seed_text)
        self.assertIn('query="discrete-input:1:BOOL"', seed_text)
        self.assertIn("PLC4J requests: 2", projection_out)

    def test_codesys_application_generation_rejects_duplicate_fsm_call_sequence(self) -> None:
        session_dir = self.init_session_from_fixture("multi-subsystem-valid")
        run_ok(
            PYTHON,
            "skills/moqui-device-seed-designer/scripts/render_seed_from_surveys.py",
            "--session-dir",
            str(session_dir),
        )
        fsm_path = session_dir / "survey-answers" / "main-fsm-survey.yaml"
        fsm_path.write_text(fsm_path.read_text(encoding="utf-8").replace("call_sequence: 20", "call_sequence: 10"), encoding="utf-8")
        result = run_fail(
            PYTHON,
            "skills/moqui-plc-designer/scripts/render_codesys_applications.py",
            "--session-dir",
            str(session_dir),
            "--no-copy-framework",
        )
        self.assertIn("duplicate subsystem call_sequence", result.stderr)

    def test_atomic_component_library_catalog_covers_all_atomic_models(self) -> None:
        catalog_path = REPO_ROOT / "skills" / "moqui-device-seed-designer" / "references" / "atomic-component-library.json"
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        components = catalog["components"]
        self.assertEqual(
            set(components.keys()),
            {"actuator", "actuator_group", "axis", "axis_group", "process_pid", "signal_mgmt"},
        )
        self.assertEqual(components["actuator"]["logicalModel"], "Actuator")
        self.assertIn("configRecipe", components["process_pid"]["parameterGroups"])
        self.assertIn("runtimeStatus", components["signal_mgmt"]["parameterGroups"])

    def test_atomic_component_library_renders_cloneable_actuator_template(self) -> None:
        tmp_root = Path(tempfile.mkdtemp(prefix="agent-skills-atomic-"))
        self.addCleanup(lambda: shutil.rmtree(tmp_root, ignore_errors=True))
        output_path = tmp_root / "actuator-template.xml"
        spec_path = tmp_root / "actuator-template-spec.json"

        run_ok(
            PYTHON,
            "skills/moqui-device-seed-designer/scripts/render_atomic_component_template.py",
            "actuator",
            "--include-config",
            "--set",
            "ACTUATOR_DEVICE_ID=UV_LAMP_01",
            "--set",
            "ACTUATOR_NAME=UV Lamp 01",
            "--set",
            "PARENT_DEVICE_ID=UV_LINE_PLC",
            "--set",
            "ACTUATOR_CONTROL_METHOD_ENUM_ID=DcmSingleActuationDoubleFeedback",
            "--set",
            "CONTROL_METHOD_ENUM_ID=DcmSingleActuationDoubleFeedback",
            "--output",
            str(output_path),
            "--spec-output",
            str(spec_path),
        )

        rendered = output_path.read_text(encoding="utf-8")
        bundle_spec = json.loads(spec_path.read_text(encoding="utf-8"))
        self.assertIn('deviceId="UV_LAMP_01"', rendered)
        self.assertIn('parameterDefId="PD_UV_LAMP_01_ENABLE"', rendered)
        self.assertIn('parameterId="P_UV_LAMP_01_ENABLE"', rendered)
        self.assertIn('deviceConfigId="CFG_UV_LAMP_01_TEMPLATE"', rendered)
        self.assertIn('deviceRuleSetId="DRS_UV_LAMP_01_TEMPLATE"', rendered)
        self.assertEqual(bundle_spec["includes"], ["actuator", "device_config", "actuator_config"])

    def test_guided_questions_for_blank_session_start_with_system_decomposition(self) -> None:
        session_dir = self.init_blank_session()
        output = run_ok(
            PYTHON,
            "skills/moqui-plant-designer/scripts/render_guided_questions.py",
            "--session-dir",
            str(session_dir),
        )
        self.assertIn("Wrote guided questions", output)
        guided_text = (session_dir / "notes" / "guided-questions.md").read_text(encoding="utf-8")
        self.assertIn("Next stage: `system_decomposition`", guided_text)
        self.assertIn("nome macchina/impianto", guided_text)

    def test_guided_questions_use_atomic_component_context_for_incomplete_signal_cabling(self) -> None:
        session_dir = self.init_session_from_fixture("gateway-valid")
        classification_path = session_dir / "survey-answers" / "elementary-device-classification-survey.yaml"
        classification_path.write_text(
            """devices:
  - device_id: LAMP_01
    parent_subsystem_id: SS_MAIN
    physical_device_name: UV Lamp 1
    logical_model: Actuator
    actuation_feedback_class: SA-DF
    control_method_enum_id: ""
    positive_logic_required: true
    expected_actuation_signals: []
    expected_feedback_signals: []
    notes: ""
""",
            encoding="utf-8",
        )
        result = run_ok(
            PYTHON,
            "skills/moqui-plant-designer/scripts/render_guided_questions.py",
            "--session-dir",
            str(session_dir),
            "--json",
        )
        summary = json.loads(result)
        self.assertEqual(summary["stage"], "signal_catalog")
        joined = "\n".join(item["question"] + " " + item["why"] for item in summary["questions"])
        self.assertIn("attesi almeno 1 attuazioni e 2 feedback", joined)
        self.assertIn("parametri logici dell'atomic component sono gia fissati dal modello", joined)

    def test_transport_projection_accepts_real_plc4j_seed(self) -> None:
        plc4j_seed = REPO_ROOT.parents[1] / "moqui-plc4j" / "data" / "Plc4jTestData.xml"
        output = run_ok(
            PYTHON,
            "skills/moqui-device-seed-designer/scripts/validate_transport_projection.py",
            "--seed",
            str(plc4j_seed),
        )
        self.assertIn("Transport projection validated.", output)
        self.assertIn("PLC4J requests:", output)

    def test_transport_projection_rejects_seed_without_gateway_or_plc4j(self) -> None:
        session_dir = self.init_session_from_fixture("gateway-valid")
        seed_path = session_dir / "seed-data" / "manual-seed.xml"
        seed_path.parent.mkdir(parents=True, exist_ok=True)
        seed_path.write_text(
            """<?xml version="1.0" encoding="UTF-8"?>
<entity-facade-xml type="seed">
    <moqui.device.Device deviceId="PLC_ONLY" deviceTypeEnumId="DtPLC"/>
    <moqui.device.PhysicalDevice deviceId="PLC_ONLY" deviceName="PLC Only"/>
</entity-facade-xml>
""",
            encoding="utf-8",
        )
        result = run_fail(
            PYTHON,
            "skills/moqui-device-seed-designer/scripts/validate_transport_projection.py",
            "--seed",
            str(seed_path),
        )
        self.assertIn("No transport projection found", result.stderr)

    def test_transport_architecture_requires_valid_mode(self) -> None:
        session_dir = self.init_session_from_fixture("gateway-valid")
        (session_dir / "survey-answers" / "transport-architecture-survey.yaml").write_text(
            """transport_architecture:
  primary_transport_mode: unsupported-mode
  allows_hybrid_projection: false
gateway_projection:
  required: false
  rationale: ""
plc4j_projection:
  required: false
  default_run_service_name: moqui.plc4j.Plc4jServices.run#Plc4jRequest
  connection_strategy: ""
  notes: ""
""",
            encoding="utf-8",
        )
        result = run_fail(
            PYTHON,
            "skills/moqui-plant-designer/scripts/validate_upstream_surveys.py",
            str(session_dir),
        )
        self.assertIn("primary_transport_mode as gateway, plc4j, or hybrid", result.stderr)

    def test_invalid_yaml_is_reported_clearly(self) -> None:
        session_dir = self.init_session_from_fixture("gateway-valid")
        (session_dir / "survey-answers" / "system-decomposition-survey.yaml").write_text(
            "project_scope:\n  machine_name: Test\nsystem_tree:\n  - subsystem_id: SS1\n    subsystem_name: Main\n    subsystem_type: Machine\n  - invalid: [unterminated\n",
            encoding="utf-8",
        )

        result = run_fail(
            PYTHON,
            "skills/moqui-plant-designer/scripts/validate_upstream_surveys.py",
            str(session_dir),
        )
        self.assertIn("Invalid YAML in system-decomposition-survey.yaml", result.stderr)

    def test_unsupported_logical_model_fails_fast(self) -> None:
        session_dir = self.init_session_from_fixture("gateway-valid")
        (session_dir / "survey-answers" / "elementary-device-classification-survey.yaml").write_text(
            """devices:
  - device_id: DEV1
    parent_subsystem_id: SS_MAIN
    physical_device_name: Dev1
    logical_model: FancyRobot
    actuation_feedback_class: SA-NO
    positive_logic_required: true
    expected_actuation_signals: [CMD1]
    expected_feedback_signals: []
""",
            encoding="utf-8",
        )

        result = run_fail(
            PYTHON,
            "skills/moqui-plant-designer/scripts/validate_upstream_surveys.py",
            str(session_dir),
        )
        self.assertIn("unsupported logical_model FancyRobot", result.stderr)

    def test_unsupported_iec_type_fails_fast(self) -> None:
        session_dir = self.init_session_from_fixture("gateway-valid")
        (session_dir / "survey-answers" / "signal-catalog-survey.yaml").write_text(
            """naming_rules:
  positive_logic_default: true
signals:
  - signal_id: SIG1
    device_id: LAMP_01
    signal_name: cmd1
    direction: output
    signal_kind: analog
    iec_type: LINT
    source_rule: test
""",
            encoding="utf-8",
        )

        result = run_fail(
            PYTHON,
            "skills/moqui-plant-designer/scripts/validate_upstream_surveys.py",
            str(session_dir),
        )
        self.assertIn("unsupported iec_type LINT", result.stderr)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
import json
import csv
import re
import xml.etree.ElementTree as ET
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

    def test_session_bootstraps_portable_architecture_context(self) -> None:
        session_dir = self.init_blank_session("architecture-context")
        context_path = session_dir / "notes" / "project-architecture-context.md"
        self.assertTrue(context_path.is_file())
        context = context_path.read_text(encoding="utf-8")
        self.assertIn("## Naming boundary", context)
        self.assertIn("never store `dev.coldGlycolPump`", context)
        session = json.loads((session_dir / "session.json").read_text(encoding="utf-8"))
        self.assertEqual(
            "notes/project-architecture-context.md",
            session["paths"]["architectureContext"],
        )

    def test_repository_bootstrap_routes_active_session_and_component_knowledge(self) -> None:
        agents_text = (REPO_ROOT.parent / "AGENTS.md").read_text(encoding="utf-8")
        current_session = (REPO_ROOT / "CURRENT_SESSION").read_text(encoding="utf-8").strip()
        self.assertTrue(current_session)
        self.assertTrue((REPO_ROOT / "output" / "sessions" / current_session / "session.json").is_file())
        self.assertIn("agent-skills/CURRENT_SESSION", agents_text)
        for reference_name in (
            "moqui-math-knowledge.md",
            "moqui-device-knowledge.md",
            "moqui-device-gateway-knowledge.md",
            "moqui-plc-knowledge.md",
        ):
            self.assertIn(reference_name, agents_text)
            self.assertTrue(
                (REPO_ROOT / "skills" / "moqui-plant-designer" / "references" / reference_name).is_file()
            )

    def test_hvac_inbound_mappers_match_live_request_whitelist(self) -> None:
        seed_path = REPO_ROOT / "output" / "sessions" / "hvac-e2e-20260716" / "seed-data" / "HVACDemoData.xml"
        root = ET.parse(seed_path).getroot()
        expected = [
            element.attrib["requestItemName"]
            for element in root
            if element.tag.endswith("DeviceRequestItem")
            and element.attrib.get("requestName") == "HVAC_DEMO_LiveParametersWrite"
        ]
        self.assertEqual(20, len(expected))

        plc_root = REPO_ROOT.parent
        st_text = (
            plc_root
            / "iec61131/moqui/runtime/component/mantle-hvac/src/main/org/moqui/util/json/JsonToParametersMapper.st"
        ).read_text(encoding="utf-8").split("(* --- 6-DOF", 1)[0]
        c_text = (
            plc_root
            / "iot-firmware/components/moqui/runtime/component/mantle-hvac/src/main/org/moqui/util/json/JsonToParametersMapper.c"
        ).read_text(encoding="utf-8")
        st_keys = re.findall(r'(?:IF|ELSIF) jsonKey = "([^"]+)"', st_text)
        c_keys = re.findall(r'^\s*\{ "([^"]+)"\s*,\s*offsetof', c_text, re.MULTILINE)
        self.assertEqual(expected, st_keys)
        self.assertEqual(expected, c_keys)

    def test_parameter_publisher_is_opt_in_documentation_template(self) -> None:
        plc_root = REPO_ROOT.parent
        mapper_text = (
            plc_root
            / "iec61131/moqui/runtime/component/mantle-hvac/src/main/org/moqui/util/json/ParametersToJsonMapper.st"
        ).read_text(encoding="utf-8")
        executable_text = re.sub(r'\(\*.*?\*\)', '', mapper_text, flags=re.DOTALL)
        self.assertNotIn("SetKeyWithValue", executable_text)

        ec_text = (
            plc_root / "iec61131/moqui/framework/src/main/org/moqui/context/ec.st"
        ).read_text(encoding="utf-8")
        self.assertIn("paramsPubEnable : BOOL := FALSE;", ec_text)

        c_mapper = (
            plc_root
            / "iot-firmware/components/moqui/runtime/component/mantle-hvac/src/main/org/moqui/util/json/ParametersToJsonMapper.c"
        ).read_text(encoding="utf-8")
        c_context = (
            plc_root / "iot-firmware/components/moqui/framework/src/main/org/moqui/context/ec.c"
        ).read_text(encoding="utf-8")
        iot_main = (plc_root / "iot-firmware/main/main.c").read_text(encoding="utf-8")
        self.assertIn("#if 0", c_mapper)
        self.assertIn("return false;", c_mapper)
        self.assertIn(".paramsPubEnable = false", c_context)
        self.assertIn("connected && ec.paramsPubEnable", iot_main)

    def test_hvac_parameter_logger_matches_modeled_numeric_parameters(self) -> None:
        plc_root = REPO_ROOT.parent
        seed_path = plc_root.parent / "moqui-device" / "data" / "HVACDemoData.xml"
        root = ET.parse(seed_path).getroot()
        expected = [
            element.attrib["parameterId"]
            for element in root
            if element.tag.endswith("Parameter")
            and element.attrib.get("deviceId") == "HVAC_DEMO_PLC"
            and "numericValue" in element.attrib
        ]
        self.assertEqual(29, len(expected))

        logger_text = (
            plc_root
            / "iec61131/moqui/runtime/component/mantle-hvac/src/main/mantle/hvac/ParameterLogger.st"
        ).read_text(encoding="utf-8")
        sources = re.findall(r"source := '([^']+)'", logger_text)
        self.assertEqual(expected, sources)
        self.assertIn("clks : Clocks;", logger_text)
        self.assertIn("NOT clks.clock1minute", logger_text)
        self.assertIn("componentName : STRING := 'HVAC_DEMO_PLC';", logger_text)

        main_text = (
            plc_root / "iec61131/moqui/runtime/component/mantle-hvac/src/main/mantle/hvac/Main.st"
        ).read_text(encoding="utf-8")
        self.assertLess(
            main_text.index("deviceManager(operationType := operationType);"),
            main_text.index("logParameters(operationType := operationType);"),
        )

    def test_hvac_thermostat_band_is_separate_from_absolute_limits(self) -> None:
        plc_root = REPO_ROOT.parent
        iec = (
            plc_root / "iec61131/moqui/runtime/component/mantle-hvac/src/main/mantle/hvac/MainRuleEngine.st"
        ).read_text(encoding="utf-8")
        ax = (
            plc_root / "simatic-ax/src/moqui/runtime/component/mantle-hvac/src/main/mantle/hvac/MainRuleEngine.st"
        ).read_text(encoding="utf-8")
        iot = (
            plc_root / "iot-firmware/components/moqui/runtime/component/mantle-hvac/src/main/mantle/hvac/MainRuleEngine.c"
        ).read_text(encoding="utf-8")
        iot_manual = (
            plc_root / "iot-firmware/src-manual/runtime/component/mantle-hvac/src/main/mantle/hvac/MainRuleEngine.c"
        ).read_text(encoding="utf-8")

        for text in (iec, ax):
            self.assertIn("AND dev.tempAboveSetpointBand THEN", text)
            self.assertIn("AND dev.tempBelowSetpointBand THEN", text)
            self.assertIn("IF dev.tempBelowSetpointBand OR dev.isCompleted THEN", text)
            self.assertIn("IF dev.isCompleted OR dev.tempAboveSetpointBand THEN", text)
            self.assertIn("ELSIF dev.tempOverMax THEN", text)
            self.assertIn("ELSIF dev.tempUnderMin THEN", text)

        for text in (iot, iot_manual):
            self.assertIn("&& dev->tempAboveSetpointBand)", text)
            self.assertIn("&& dev->tempBelowSetpointBand)", text)
            self.assertIn("if (dev->tempBelowSetpointBand || dev->isCompleted)", text)
            self.assertIn("if (dev->isCompleted || dev->tempAboveSetpointBand)", text)
            self.assertIn("else if (dev->tempOverMax)", text)
            self.assertIn("else if (dev->tempUnderMin)", text)

    def test_plc_logger_identity_uses_model_ids_without_concatenation(self) -> None:
        plc_root = REPO_ROOT.parent
        conf_text = (
            plc_root / "iec61131/moqui/framework/src/main/resources/MoquiConf.st"
        ).read_text(encoding="utf-8")
        actuator_text = (
            plc_root / "iec61131/moqui/framework/src/main/org/moqui/device/Actuator.st"
        ).read_text(encoding="utf-8")
        pid_text = (
            plc_root / "iec61131/moqui/framework/src/main/org/moqui/device/ProcessPid.st"
        ).read_text(encoding="utf-8")
        self.assertIn("applicationDeviceId : STRING := 'HVAC_DEMO_PLC';", conf_text)
        self.assertIn("loggerName := actuatorId;", actuator_text)
        self.assertIn("loggerName := controlSystemId;", pid_text)
        self.assertNotIn("actuatorName, '['", actuator_text)
        self.assertNotIn("controlSystemName, '['", pid_text)

        for recipe_name in (
            "CivilCooling.HvacDeviceConfig.txtrecipe",
            "CivilHeating.HvacDeviceConfig.txtrecipe",
            "CivilDehumidifying.HvacDeviceConfig.txtrecipe",
        ):
            recipe_text = (
                plc_root / "iec61131/moqui/runtime/component/mantle-hvac/data" / recipe_name
            ).read_text(encoding="utf-8")
            self.assertIn("actuatorId:='HVAC_COLD_GLYCOL_PUMP'", recipe_text)
            self.assertIn("controlSystemId:='HVAC_AHU_FAN'", recipe_text)

    def test_simatic_ax_logger_projection_uses_exact_model_ids(self) -> None:
        plc_root = REPO_ROOT.parent
        ax_root = plc_root / "simatic-ax"
        parameter_logger = (
            ax_root / "src/moqui/runtime/component/mantle-hvac/src/main/mantle/hvac/ParameterLogger.st"
        ).read_text(encoding="utf-8")
        seed_root = ET.parse(
            plc_root.parent / "moqui-device" / "data" / "HVACDemoData.xml"
        ).getroot()
        expected = [
            element.attrib["parameterId"]
            for element in seed_root
            if element.tag.endswith("Parameter")
            and element.attrib.get("deviceId") == "HVAC_DEMO_PLC"
            and "numericValue" in element.attrib
        ]
        self.assertEqual(expected, re.findall(r"source := '([^']+)'", parameter_logger))

        configuration = (ax_root / "src/configuration.st").read_text(encoding="utf-8")
        actuator = (
            ax_root / "src/moqui/framework/src/main/org/moqui/device/Actuator.st"
        ).read_text(encoding="utf-8")
        pid = (
            ax_root / "src/moqui/framework/src/main/org/moqui/device/ProcessPid.st"
        ).read_text(encoding="utf-8")
        main = (
            ax_root / "src/moqui/runtime/component/mantle-hvac/src/main/mantle/hvac/Main.st"
        ).read_text(encoding="utf-8")
        self.assertIn("applicationDeviceId : STRING := 'HVAC_DEMO_PLC';", configuration)
        self.assertIn("loggerName := actuatorId;", actuator)
        self.assertIn("loggerName := controlSystemId;", pid)
        self.assertLess(
            main.index("deviceManager(operationType := operationType);"),
            main.index("logParameters(operationType := operationType);"),
        )
        for recipe_path in (
            ax_root / "src/moqui/runtime/component/mantle-hvac/data"
        ).glob("Civil*.axrecipe"):
            recipe_text = recipe_path.read_text(encoding="utf-8")
            self.assertIn("STRING;HVAC_COLD_GLYCOL_PUMP", recipe_text)
            self.assertIn("STRING;HVAC_AHU_FAN", recipe_text)

    def test_iot_logger_projection_preserves_scope_and_complete_snapshot(self) -> None:
        plc_root = REPO_ROOT.parent
        iot_root = plc_root / "iot-firmware"
        seed_root = ET.parse(
            plc_root.parent / "moqui-device" / "data" / "HVACDemoData.xml"
        ).getroot()
        expected = [
            element.attrib["parameterId"]
            for element in seed_root
            if element.tag.endswith("Parameter")
            and element.attrib.get("deviceId") == "HVAC_DEMO_PLC"
            and "numericValue" in element.attrib
        ]

        parameter_logger = (
            iot_root
            / "components/moqui/runtime/component/mantle-hvac/src/main/mantle/hvac/ParameterLogger.c"
        ).read_text(encoding="utf-8")
        self.assertEqual(expected, re.findall(r'LOG_NUMERIC\("([^"]+)"', parameter_logger))

        logger_facade = (
            iot_root / "components/moqui/framework/src/main/org/moqui/context/LoggerFacade.c"
        ).read_text(encoding="utf-8")
        self.assertIn("ev->source[0] = '\\0';", logger_facade)
        self.assertIn("strncpy(ev->source, source", logger_facade)
        self.assertIn("#define LOG_RING_CAPACITY (LOG_MAX_SIZE)", logger_facade)
        self.assertIn("s_ring_count = (uint16_t)(s_ring_count - n);", logger_facade)
        configuration = (
            iot_root / "components/moqui/framework/src/main/resources/MoquiConf.h"
        ).read_text(encoding="utf-8")
        self.assertIn('#define MOQUI_APPLICATION_DEVICE_ID "HVAC_DEMO_PLC"', configuration)

        actuator = (
            iot_root / "components/moqui/framework/src/main/org/moqui/device/Actuator.c"
        ).read_text(encoding="utf-8")
        pid = (
            iot_root / "components/moqui/framework/src/main/org/moqui/device/ProcessPid.c"
        ).read_text(encoding="utf-8")
        main = (
            iot_root / "components/moqui/runtime/component/mantle-hvac/src/main/mantle/hvac/Main.c"
        ).read_text(encoding="utf-8")
        self.assertIn("LoggerFacade_Init(&self->logger, self->actuatorId);", actuator)
        self.assertIn("LoggerFacade_Init(&self->logger, self->controlSystemId);", pid)
        self.assertLess(
            main.index("DeviceManager_Update(dev, clks, operationType);"),
            main.index("ParameterLogger_Update(dev, clks, operationType);"),
        )

        duplicate_pairs = (
            ("framework/src/main/org/moqui/context/LoggerFacade.c", "framework/src/main/org/moqui/context/LoggerFacade.c"),
            ("framework/src/main/org/moqui/context/LoggerFacade.h", "framework/src/main/org/moqui/context/LoggerFacade.h"),
            ("framework/src/main/org/moqui/device/Actuator.c", "framework/src/main/org/moqui/device/Actuator.c"),
            ("framework/src/main/org/moqui/device/ActuatorGroup.c", "framework/src/main/org/moqui/device/ActuatorGroup.c"),
            ("framework/src/main/org/moqui/device/DeviceConfigCmds.c", "framework/src/main/org/moqui/device/DeviceConfigCmds.c"),
            ("framework/src/main/org/moqui/device/DeviceConfigMgmt.c", "framework/src/main/org/moqui/device/DeviceConfigMgmt.c"),
            ("framework/src/main/org/moqui/device/ProcessPid.c", "framework/src/main/org/moqui/device/ProcessPid.c"),
            ("framework/src/main/org/moqui/diagnostics/NetworkDiagnostics.c", "framework/src/main/org/moqui/diagnostics/NetworkDiagnostics.c"),
            ("runtime/component/mantle-hvac/src/main/mantle/hvac/Main.c", "runtime/component/mantle-hvac/src/main/mantle/hvac/Main.c"),
            ("runtime/component/mantle-hvac/src/main/mantle/hvac/ParameterLogger.c", "runtime/component/mantle-hvac/src/main/mantle/hvac/ParameterLogger.c"),
            ("runtime/component/mantle-hvac/src/main/mantle/hvac/ParameterLogger.h", "runtime/component/mantle-hvac/src/main/mantle/hvac/ParameterLogger.h"),
            ("runtime/component/mantle-hvac/src/main/org/moqui/device/AirDistributionController.c", "runtime/component/mantle-hvac/src/main/org/moqui/device/AirDistributionController.c"),
            ("runtime/component/mantle-hvac/src/main/org/moqui/device/DeviceDiagnostics.c", "runtime/component/mantle-hvac/src/main/org/moqui/device/DeviceDiagnostics.c"),
        )
        for component_path, manual_path in duplicate_pairs:
            component_text = (iot_root / "components/moqui" / component_path).read_text(encoding="utf-8")
            manual_text = (iot_root / "src-manual" / manual_path).read_text(encoding="utf-8")
            self.assertEqual(component_text, manual_text, component_path)

        for name in ("InputSignalUpdate.c", "OutputSignalUpdate.c"):
            component_text = (
                iot_root / "components/moqui/framework/src/main/org/moqui/device" / name
            ).read_text(encoding="utf-8")
            manual_text = (
                iot_root
                / "src-manual/runtime/component/mantle-hvac/src/main/org/moqui/device"
                / name
            ).read_text(encoding="utf-8")
            self.assertEqual(component_text, manual_text, name)

        for recipe_path in (
            iot_root / "components/moqui/runtime/component/mantle-hvac/data"
        ).glob("Phase*.HvacDeviceConfig.json"):
            recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
            self.assertEqual("HVAC_COLD_GLYCOL_PUMP", recipe["coldGlycolPump"]["actuatorId"])
            self.assertEqual("HVAC_AHU_FAN", recipe["ahuFan"]["controlSystemId"])

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
        self.assertIn('deviceId="UV_LINE_PLC" deviceName="UV Line CODESYS Application" softwareApplication="UvApplication"', seed_text)
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
        self.assertIn('parameterId="P_LAMP_01_REF"', seed_text)
        self.assertIn('requestItemName="powerReference"', seed_text)
        self.assertIn('deviceConfigId="CFG_LAMP_01_PRODUCTION"', seed_text)
        self.assertIn('deviceRuleSetId="DRS_UV_LINE_PRODUCTION"', seed_text)
        self.assertIn('deviceRuleId="DR_UV_LINE_LAMP_010"', seed_text)
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
        cure_mapper = (cure_component / "src" / "main" / "org" / "moqui" / "util" / "json" / "JsonToParametersMapper.st").read_text(encoding="utf-8")
        cure_manifest = json.loads((applications_root / "CureApplication" / "application-manifest.json").read_text(encoding="utf-8"))
        self.assertIn("dev.uvLampBankGroupEnable := TRUE;", cure_main)
        self.assertIn("(* No fault state defined for this FSM. *)", cure_main)
        self.assertNotIn("IF dev.faultRequest THEN dev.status := MainStatus.Curing", cure_main)
        self.assertIn("dev.cureLampStatus := CureLampStatus.Active;", cure_controller)
        self.assertIn("uvLampBank : ActuatorGroup;", cure_facade)
        self.assertIn('jsonKey = "lampPowerReference"', cure_mapper)
        self.assertIn("dev.uvLampBankDemandSetpoint := TO_REAL(jsonValue.value.lrValue);", cure_mapper)
        self.assertIn("P_UV_LAMP_BANK_DEMAND_SETPOINT", cure_mapper)
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
        self.assertIn('workEffortTypeEnumId="WetProject"', wiki_seed)
        self.assertIn('workEffortTypeEnumId="WetMilestone"', wiki_seed)
        self.assertIn('workEffortTypeEnumId="WetTask"', wiki_seed)
        self.assertEqual(wiki_seed.count('workEffortAssocTypeEnumId="WeatMilestone"'), 8)

    def test_final_seed_requires_explicit_approvals_but_draft_is_available(self) -> None:
        session_dir = self.init_session_from_fixture("gateway-valid")
        approval_path = session_dir / "survey-answers" / "approval-survey.yaml"
        approval_path.write_text(approval_path.read_text(encoding="utf-8").replace(
            "seed_generation_approved: true", "seed_generation_approved: false"
        ), encoding="utf-8")
        result = run_fail(PYTHON, "skills/moqui-device-seed-designer/scripts/render_seed_from_surveys.py",
                          "--session-dir", str(session_dir))
        self.assertIn("seed_generation_approved", result.stderr)
        run_ok(PYTHON, "skills/moqui-device-seed-designer/scripts/render_seed_from_surveys.py",
               "--session-dir", str(session_dir), "--draft")

    def test_eplan_extractor_preserves_source_rows_without_classifying_devices(self) -> None:
        tmp_root = Path(tempfile.mkdtemp(prefix="eplan-extractor-test-"))
        self.addCleanup(lambda: shutil.rmtree(tmp_root, ignore_errors=True))
        csv_path = tmp_root / "panel.csv"
        properties = [""] * 267
        properties[167] = "P_INSTANCE_PAGEFULLNAME"
        properties[184] = "P_FUNC_DEVICETAG_FULLNAME"
        properties[261] = "P_ARTICLE_TYPENR"
        properties[262] = "P_ARTICLE_ORDERNR"
        properties[263] = "P_ARTICLE_DESCR1"
        properties[264] = "P_ARTICLE_DESCR2"
        properties[265] = "P_ARTICLE_DESCR3"
        properties[266] = "P_ARTICLE_MANUFACTURER"
        values = [""] * 267
        values[167], values[184], values[262], values[266] = "=A/1", "=A+R1-K1", "6ES7-TEST", "SIE"
        with csv_path.open("w", encoding="utf-16", newline="") as stream:
            writer = csv.writer(stream, delimiter=";")
            writer.writerow(["device/part"] * 267)
            writer.writerow(properties)
            writer.writerow(values)
        output_dir = tmp_root / "review"
        run_ok(PYTHON, "skills/moqui-plant-designer/scripts/analyze_eplan_sources.py",
               "--csv", str(csv_path), "--output-dir", str(output_dir))
        payload = json.loads((output_dir / "eplan-review-candidates.json").read_text(encoding="utf-8"))
        self.assertFalse(payload["authoritative"])
        self.assertEqual(payload["candidates"][0]["source_row"], 3)
        self.assertEqual(payload["candidates"][0]["device_tag"], "=A+R1-K1")
        self.assertEqual(payload["candidates"][0]["proposed_device_class"], "")

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

    def test_process_pid_fixture_has_no_duplicate_fields_and_correct_wiring(self) -> None:
        # Regression fixture for three bugs found while building a real
        # ProcessPid-based Application (tank-level-control-001):
        #   1. render_parameter_declarations() and render_atomic_device_blocks()
        #      independently declared the same DeviceFacade field, producing
        #      an invalid IEC 61131-3 STRUCT with duplicate member names.
        #   2. infer_process_pid_fields() matched by substring
        #      ("setpoint" in "At Setpoint") and by purpose_enum_id alone,
        #      wiring DeviceManager.pou's feedback/setpoint arguments to the
        #      wrong Parameter -- silently, with no compile error.
        #   3. The ProcessPid clock argument was hardcoded to clock100ms
        #      regardless of the configured tickTime (10ms here).
        session_dir = self.init_session_from_fixture("process-pid-valid")

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
            "skills/moqui-plc-designer/scripts/render_codesys_applications.py",
            "--session-dir",
            str(session_dir),
            "--no-copy-framework",
        )

        component_root = (
            session_dir / "generated-plc" / "codesys-applications" / "TankLevelControl"
            / "runtime" / "component" / "main"
        )
        facade_text = (
            component_root / "src" / "main" / "org" / "moqui" / "device" / "DeviceFacade.dut"
        ).read_text(encoding="utf-8")
        manager_text = (
            component_root / "src" / "main" / "org" / "moqui" / "device" / "DeviceManager.pou"
        ).read_text(encoding="utf-8")

        names: list[str] = []
        for line in facade_text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("(*") or " : " not in stripped:
                continue
            names.append(stripped.split(" : ", 1)[0])
        duplicates = sorted({name for name in names if names.count(name) > 1})
        self.assertEqual([], duplicates, f"DeviceFacade.dut declares duplicate fields: {duplicates}")

        self.assertIn("feedback := dev.levelControllerFeedback,", manager_text)
        self.assertIn("setpoint := dev.levelControllerSetpoint,", manager_text)
        self.assertNotIn("feedback := dev.levelControllerLevelHighHighThreshold,", manager_text)
        self.assertNotIn("setpoint := dev.levelControllerAtSetpoint,", manager_text)
        self.assertIn("clock := clks.clock10ms,", manager_text)

        cross_check_out = run_ok(
            PYTHON,
            "skills/moqui-plc-designer/scripts/validate_generated_plc_against_seed.py",
            str(session_dir / "seed-data" / "survey-derived-seed.xml"),
            "--device-id",
            "DG_TANK_LEVEL_CTRL",
            "--allow-logical-root",
            "--component-root",
            str(component_root),
        )
        self.assertIn("Generated PLC cross-check passed.", cross_check_out)

    def test_manual_fault_ack_fixture_declares_and_wires_faultAck(self) -> None:
        # Regression fixture for a fourth bug found while building a second
        # real ProcessPid Application (an isothermal-reactor concentration
        # loop with a manual fault-acknowledge recovery policy instead of
        # auto-clear): render_device_catalog_from_seed.py's
        # render_state_request_declarations() reserved "resetRequest" as its
        # extra state-request field, while render_statusflow_templates.py's
        # same-named function (used to build MainRuleEngine.pou/Main.pou via
        # render_codesys_applications.py) reserved "faultAck" instead. Any
        # FSM survey using dev.faultAck for a manual-recovery transition
        # generated a MainRuleEngine.pou assigning a DeviceFacade field that
        # DeviceFacade.dut never declared.
        session_dir = self.init_session_from_fixture("manual-fault-ack-valid")

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
            "skills/moqui-plc-designer/scripts/render_codesys_applications.py",
            "--session-dir",
            str(session_dir),
            "--no-copy-framework",
        )

        component_root = (
            session_dir / "generated-plc" / "codesys-applications" / "IsothermalReactorControl"
            / "runtime" / "component" / "main"
        )
        facade_text = (
            component_root / "src" / "main" / "org" / "moqui" / "device" / "DeviceFacade.dut"
        ).read_text(encoding="utf-8")
        rule_engine_text = (
            component_root / "src" / "main" / "mantle" / "main" / "MainRuleEngine.pou"
        ).read_text(encoding="utf-8")

        self.assertIn("faultAck : BOOL;", facade_text)
        self.assertIn("dev.faultAck AND", rule_engine_text)
        self.assertIn("dev.faultAck := FALSE;", rule_engine_text)

        cross_check_out = run_ok(
            PYTHON,
            "skills/moqui-plc-designer/scripts/validate_generated_plc_against_seed.py",
            str(session_dir / "seed-data" / "survey-derived-seed.xml"),
            "--device-id",
            "DG_REACTOR_CTRL",
            "--allow-logical-root",
            "--component-root",
            str(component_root),
        )
        self.assertIn("Generated PLC cross-check passed.", cross_check_out)


if __name__ == "__main__":
    unittest.main()

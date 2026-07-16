# Moqui Framework for PLC

[![license](http://img.shields.io/badge/license-CC0%201.0%20Universal-blue.svg)](https://github.com/moqui/moqui-plc/blob/master/LICENSE.md)

**The first model-driven, no-code/low-code approach to industrial automation where
the PLC program is a projection of a universal data model — not a
hand-drawn control diagram.**

Moqui Framework for PLC is an IEC 61131-3 framework for building machine and
process applications around reusable motion, device, logging, diagnostics, and
MQTT components. What makes it different from a conventional function-block
library is that the orchestration on top of those components — the state machines,
the sequencing, the operating modes — is **AI-assisted and generated from the
[moqui-device](https://github.com/moqui/moqui-device) data model**, not drawn by
hand in a vendor IDE.

## Why this is new

Generating PLC code from a model is not new in itself: tools like Simulink PLC
Coder have produced IEC 61131-3 from control diagrams and state charts for years.
They all start from a **control model** — a block diagram or a state machine drawn
specifically to be compiled down.

`moqui-plc` starts somewhere else: from a **universal data model**. The
devices, parameters, requests, and state machines already live in the same
relational schema that governs maintenance, configuration, recipes, audit, and
lifecycle — the Silverston-lineage model inherited through OFBiz/Moqui. The PLC
program is a *runtime projection of that model*, the same way
[moqui-device-gateway](https://github.com/moqui/moqui-device-gateway) projects the
same model into Apache Camel edge routes.

That is the claim worth making: not one more code generator fed by a diagram, but
the **first no-code/low-code automation where the controller is generated from the
enterprise model of the plant itself** — so the running PLC, its maintenance
history, its configuration governance, and its audit trail are all faces of one
source of truth, instead of separate artifacts kept in uneasy sync. The orchestration logic
is produced from the Moqui `StatusFlow`
entities (defined in `BasicEntities.xml` of moqui-framework) combined with the
`moqui-device` model, through model-driven templates an AI agent fills against the
declared data — under human approval, with the change tracked. The field engineer
still adds the genuinely site-specific edges (`InputSignalUpdate`,
`OutputSignalUpdate`, physical terminal mapping): the skill is not removed, it is
focused on what only a human at the machine can decide.

## Core motion and device abstractions

A whole plant reduces to a small set of reusable function blocks — a Hardware
Abstraction Layer — parameterised by data:

- `Axis`: a single-axis wrapper around PLCopen Motion Control Part 1/2 function blocks for servo drives and motors.
- `AxisGroup`: a coordinated multi-axis wrapper around PLCopen Motion Control Part 4 for robot and kinematic groups.
- `Actuator`: a bistable device controller with handshake-based enable/disable sequencing and diagnostics.
- `ActuatorGroup`: a demand-driven group controller for multiple bistable actuators, with staging, anti-cycling delays, and wear-balancing rotation.
- `ProcessPid`: for modulating devices.
- `SignalMgmt`: signal conditioning, scaling, debouncing, and filtering.
...

Typical robot use cases include conveyors with cutters, pick-and-place cells,
tripod/robot-arm kinematics, and coordinated axis groups driven through a common
FSM-oriented application layer.

The repository also contains `mantle-hvac`, an application example showing how the
framework can be used outside robotics to orchestrate HVAC equipment, device
rules, and supervisory state machines on top of the same reusable PLC components.

### mantle-hvac — civil HVAC AHU example

`mantle-hvac` implements a supervisor FSM for a civil/commercial air-handling unit
(AHU) with a chilled-water cooling coil, a hot-water heating coil, supply-air fan
(with PID speed control), air-flow distributor, and duct T+RH safety monitoring.
The six operating modes (thermostat cooling, cooling with RH dehumidification,
winter heating, heating with RH control, interval dehumidification, RH-target
dehumidification) and the duct safety alarms directly correspond to the control
sequences described in the following publicly available standards and references:

| Aspect | Standard / Reference |
|---|---|
| AHU rating, duct T+RH limits | **EN 13053:2019** — Ventilation for buildings — Air handling units — Rating and performance for units, components and sections |
| HVAC control efficiency classes and FSM structure | **EN ISO 52120-1:2022** (supersedes EN 15232) — Energy performance of buildings — Contribution of building automation, controls and building management |
| Non-residential ventilation control sequences | **EN 16798-3:2017** — Energy performance of buildings — Ventilation for non-residential buildings — Performance requirements for ventilation and room-conditioning systems |
| Interval ventilation (run/break cycle, Mode E) | **EN 15665:2009+A1:2011** — Ventilation for buildings — Determining performance criteria for residential ventilation systems |
| Thermal comfort setpoints (T, RH) | **ISO 7730:2005** — Ergonomics of the thermal environment — Analytical determination and interpretation of thermal comfort (PMV/PPD) |
| Demand-controlled ventilation / RH-target mode | **ASHRAE 62.1-2022** — Ventilation and Acceptable Indoor Air Quality in Commercial Buildings |
| VAV fan PID and duct sensor placement | **ASHRAE 90.1-2022** — Energy Standard for Buildings, Section 6.5 (HVAC controls) |
| Room automation FSM reference sequences | **VDI 3813:2011** — Room automation — HVAC functions (Raumautomation) |
| BACnet AHU operational states | **ANSI/ASHRAE 135-2020** — BACnet — A Data Communication Protocol for Building Automation and Control Networks (AHU object, operational state machine) |
| Semantic equipment tagging (ductTemp, ahuFan) | **Project Haystack v4.0** — https://project-haystack.org — open standard for tagging HVAC/BMS equipment |
| Building system ontology (AHU->fan->zone topology) | **BRICK Schema v1.3** — https://brickschema.org — open-source ontology for building systems |

The `HvacTestSuite` covers all 32 pass criteria automatically (Init, Standby,
Ventilation, Cooling, Heating, Drying, run/break, thermostat re-activation, duct
safety alarms, Fault recovery, and AirDistributionController high/low air-throw
switching) and is the regression baseline for any change to the framework or the
application layer.

## Source layout

- `iec61131/moqui/framework/src/main`: reusable framework POUs, DUTs, GVLs, and utilities.
- `iec61131/moqui/framework/src/test`: motion, device, and pick-and-place test suites.
- `iec61131/moqui/runtime/component/mantle-hvac`: example runtime component built on the framework.

The IEC 61131-3 source exports under `iec61131/moqui` can be imported into any
compliant IDE (CODESYS, Siemens AX, etc.). The repository also includes
`moqui.projectarchive`, a ready-to-open CODESYS project archive that can be used
for demos, manual validation, and automated test execution.


## Project Structure and Platform Ports

The project is composed of the canonical IEC 61131-3 implementation and its derived platform-specific ports, alongside developer workflow utilities:

- **[iec61131](iec61131/moqui)**: The canonical source of truth for the PLC framework and runtime components, exported as a clean, vendor-neutral IEC 61131-3 reference tree.
- **[simatic-ax](simatic-ax)**: The SIMATIC AX port, generated from the canonical `iec61131` tree with AX-specific overrides.
- **[iot-firmware](iot-firmware)**: The embedded ESP32/FreeRTOS port, compiled into binary outputs, also derived from the canonical `iec61131` tree.
- **[agent-skills](agent-skills)**: A model-first, data-driven low-code/no-code solution for system decomposition, survey validation, Moqui XML seed rendering, HiveMind project setup, and reviewed PLC artifact generation.

For details, requirements, and guides specific to each of these sub-projects, please refer to their respective documentation:
- [simatic-ax README](simatic-ax/README.md)
- [iot-firmware README](iot-firmware/README.md)
- [agent-skills README](agent-skills/README.md)

### Controller and application model

Every hardware CPU and every CODESYS Application is modeled as a distinct
Moqui `Device`/`PhysicalDevice`. A CODESYS project may contain multiple
Applications, each with its own framework copy, runtime component, task
configuration and manually configured device tree. FSMs inside one Application
execute sequentially in the developer-approved invocation order.

`DeviceConfig` is atomic. Multi-device configuration is composed by an ordered
`DeviceRuleSet`/`DeviceRule` graph rooted at an explicitly modeled Device or
DeviceGroup. DeviceGroup membership and approval are developer decisions; the
agent validates and materializes them without inferring redundancy or safety
behavior.

### Canonical Source of Truth

The directory `iec61131/moqui` is the canonical source of truth for the PLC framework and runtime components. Vendor-specific implementations (`simatic-ax`, `iot-firmware`) are derived from this tree and must preserve the original structure, names, comments, state machines, and execution order wherever the target platform permits it.

The current platform paths are:

- `moqui.projectarchive`: the complete CODESYS project archive used for development,
  validation, demonstrations, and test execution;
- `iec61131/moqui`: the clean IEC 61131-3 export used as the vendor-neutral reference;
- `simatic-ax`: the SIMATIC AX port, generated from the canonical IEC tree with a
  limited set of manually maintained AX-specific overrides;
- `iot-firmware`: the embedded ESP32/FreeRTOS port and its supporting generated code;
- `agent-skills`: the low-code/no-code agent skills and templates directory.

The porting scripts must not treat a generated target as the new source of truth.
Changes are made first in the CODESYS project or canonical IEC source, then
propagated to the platform-specific ports. Files that depend on vendor libraries
or runtime-specific behavior may be preserved as explicit manual overrides.

`moqui.projectarchive` is a permanent repository artifact and must always be kept.
It is not a generated build directory and must not be removed during repository
cleanup.

`MoquiStart` is the entry-point orchestrator: it initializes clocks, diagnostics,
logging, input/output processing, configuration loading, and then dispatches the
application `Main` POU.

## Recipe Storage Path

`DeviceConfigMgmt` uses `Recipe_Management.RecipeManCommands` to load device
configurations at runtime. The CODESYS IDE Recipe Manager deploys recipe files to
`PlcLogic/` (device root) with the naming `recipes<Name>.<Definition>.txtrecipe`,
while `RecipeManCommands` searches relative to the application directory
(`PlcLogic/<AppName>/`).

To bridge this gap, `DeviceConfigCmds` calls `SetStoragePath` before every
`ReloadRecipes`. The path is configured via `deviceConfigStoragePath` in
`MoquiConf.gvl` (default: `'recipes'`).

The default value is `'../'`, which points to `PlcLogic/` (one level above the
application directory `PlcLogic/<AppName>/`). This matches where CODESYS IDE
automatically deploys recipe files when the Recipe Manager Storage "File path"
field is left empty. Recipe files are named `<RecipeName>.<Definition>.txtrecipe`
(no prefix).

Do not set a prefix in the Recipe Manager Storage "File path" field — leave it
empty. A non-empty prefix (e.g. `recipes`) becomes part of the filename, which
would require `SetStoragePath` to include that prefix as well and creates
unnecessary complexity.

After changing `deviceConfigStoragePath`, rebuild and redeploy. The CODESYS File
Manager (Tools -> Files) can be used to inspect or move recipe files on the
runtime.

## Prerequisites

To open the CODESYS project for testing, you need to download the CODESYS IDE from:

* [CODESYS Store](https://store.codesys.com/en/codesys.html)

## Demo Project Archive

Use `moqui.projectarchive` to open the full demo project directly in CODESYS.
This archive is the recommended starting point when you want to explore the
framework behavior, run the included test suites, or prepare a local demo
environment without importing the source tree manually.

## End-to-End HVAC demo

This walkthrough starts the complete local HVAC data path on one Windows
workstation. It is deliberately detailed so that a first-time user can verify
the architecture without configuring physical I/O or a real PLC.

The demo exercises two independent directions:

```text
Moqui HVAC data -> moqui-device-gateway -> Artemis MQTT -> CODESYS
CODESYS ParameterLogger -> Artemis MQTT -> moqui-device-gateway -> Moqui database
```

`mosquitto_sub` is used only as an observer. ActiveMQ Artemis remains the MQTT
v5 broker used by the gateway and PLC.

### What the HVAC demo data represents

The declaration layer is
[`moqui-device/data/HVACDemoData.xml`](https://github.com/moqui-industrial/moqui-device/blob/master/data/HVACDemoData.xml).
Before starting the programs, it is useful to understand its main records:

- `HVAC_DEMO` is the complete demonstration system.
- `HVAC_DEMO_PLC` represents the dedicated CODESYS Application/PLC CPU.
- cold, hot and air groups contain the pumps, PID valves, fan, air-flow
  actuator and dampers used by `mantle-hvac`.
- `Parameter` records describe setpoints, absolute limits, recipe timing,
  feedback and runtime values. `parameterId` is the persistent Moqui identity;
  `parameterAlias` is the corresponding `DeviceFacade` field name.
- `HvacCivilCoolingConfig`, `HvacCivilHeatingConfig` and
  `HvacCivilDehumidifyingConfig` are the application recipes. The demo uses
  deliberately short finite durations: Cooling runs for 30 seconds,
  Dehumidifying completes after 60 seconds (45 seconds of runtime followed by
  the first part of its configured break), and Heating runs for 30 seconds.
  These values make automatic recipe advancement observable without waiting
  for production-scale process times. In a real recipe, a zero process
  duration still means continuous operation with no automatic advancement.
- `HVAC_DEMO_LiveParametersWrite` contains the reviewed whitelist of 20
  parameters that may be changed live. The gateway publishes them to
  `moqui/hvac-demo/parameters/live`.
- `ParameterLogger` publishes a periodic 29-value logical snapshot. Every
  event uses `loggerName=HVAC_DEMO_PLC` and an exact `Parameter.parameterId` as
  `source`.

The normal thermostat uses `tempSetpoint +/- tempHysteresis`. `tempMin` and
`tempMax` are absolute limits, not the normal Heating/Cooling thresholds.

### 1. Prerequisites and directory layout

Install the following software:

- Docker Desktop;
- Java 21;
- CODESYS Development System and `CODESYS Control Win V3 - x64`;
- Mosquitto command-line clients (`mosquitto_sub` and `mosquitto_pub`).

This guide assumes that the repositories are sibling directories:

```text
github-moqui/
  moqui-framework/
  moqui-device/
  moqui-math/
  moqui-device-gateway/
  moqui-deploy/
  moqui-plc/
```

Install or copy `moqui-device` and `moqui-math` under
`moqui-framework/runtime/component` before loading Moqui data. The component
directories must contain their complete source trees, not only their `data`
directories.

All PowerShell commands below start from `github-moqui`. The credentials shown
are development-only defaults used by the local Compose files. Do not use them
in production.

### 2. Start PostgreSQL and load the Moqui data

Start only PostgreSQL from the industrial Compose file:

```powershell
docker compose -f .\moqui-deploy\industrial\moqui-postgres-compose.yml -p moqui up -d moqui-database
docker ps --filter "name=moqui-database"
```

Wait until the container is running, then prepare and load the Moqui database:

```powershell
Set-Location .\moqui-framework
$env:entity_ds_db_conf="postgres"
$env:entity_ds_host="127.0.0.1"
$env:entity_ds_port="5432"
$env:entity_ds_database="moqui"
$env:entity_ds_user="moqui"
$env:entity_ds_password="moqui"
.\gradlew.bat getPostgresJdbc --no-daemon
.\gradlew.bat load -Ptypes=seed-initial --no-daemon
.\gradlew.bat load -Ptypes=seed --no-daemon
Set-Location ..
```

Use `seed-initial` before `seed`: the regular device seed references setup data
created during the initial load. A correctly loaded demo contains 16 HVAC
devices, 20 live-write request items and the parameters owned by
`HVAC_DEMO_PLC`. Check them with:

```powershell
docker exec moqui-database psql -U moqui -d moqui -c "SELECT COUNT(*) AS hvac_devices FROM device WHERE device_id LIKE 'HVAC%';"
docker exec moqui-database psql -U moqui -d moqui -c "SELECT COUNT(*) AS live_items FROM device_request_item WHERE request_name='HVAC_DEMO_LiveParametersWrite';"
```

### 3. Start ActiveMQ Artemis

Start the two-node development broker configuration:

```powershell
docker compose -f .\moqui-deploy\industrial\activemq-compose.yml -p moqui-broker up -d
docker ps --filter "name=moqui-broker"
```

The primary broker exposes:

- MQTT v5 on `127.0.0.1:1883`;
- the Artemis console on <http://localhost:8161>;
- development username/password `artemis` / `artemis`.

Wait for `moqui-broker1` to report `healthy`. The backup node is useful for HA
testing but the smoke test uses only `moqui-broker1`. On Windows, an error that
mentions `/bin/bash^M` means the mounted `artemis-start.sh` or `broker.xml` was
checked out with CRLF line endings; convert those two files locally to LF and
restart the containers.

### 4. Open an MQTT observer

Open a new PowerShell terminal before publishing anything. If the Mosquitto
installation directory is not on `PATH`, use the full executable path.

```powershell
mosquitto_sub -h 127.0.0.1 -p 1883 -u artemis -P artemis -V mqttv5 -q 1 -v -t "moqui-plc" -t "moqui/hvac-demo/parameters/#"
```

Keep this terminal open. The topic prefixes printed by `-v` make it clear which
direction each message belongs to:

- `moqui/hvac-demo/parameters/live`: gateway-to-PLC live parameters;
- `moqui-plc`: PLC logs and periodic parameter snapshots.

### 5. Start moqui-device-gateway

The quick demo runs Quarkus directly on the host and uses the already loaded
Moqui PostgreSQL database. It deliberately points both the transactional and
log datasources at `moqui`; a production deployment may use a separate
`moqui-log`/TimescaleDB database.

Open another PowerShell terminal:

```powershell
Set-Location .\moqui-device-gateway
$env:QUARKUS_PROFILE="local"
$env:QUARKUS_DATASOURCE_JDBC_URL="jdbc:postgresql://localhost:5432/moqui"
$env:QUARKUS_DATASOURCE_USERNAME="moqui"
$env:QUARKUS_DATASOURCE_PASSWORD="moqui"
$env:QUARKUS_DATASOURCE_LOG_JDBC_URL="jdbc:postgresql://localhost:5432/moqui"
$env:QUARKUS_DATASOURCE_LOG_USERNAME="moqui"
$env:QUARKUS_DATASOURCE_LOG_PASSWORD="moqui"
$env:MQTT_BROKER_URL="tcp://localhost:1883"
$env:GATEWAY_DEVICE_ID="HVAC_DEMO_GATEWAY"
$env:MQTT_WRITE_AFTERPUBLISH_ENABLED="false"
.\gradlew.bat quarkusDev
```

The gateway listens on port `8081`. In a separate terminal, verify its health:

```powershell
Invoke-RestMethod http://localhost:8081/q/health
```

The status must be `UP`. `MQTT_WRITE_AFTERPUBLISH_ENABLED=false` is appropriate
only for this reduced demo, where the Moqui web runtime on port 8080 is not
running. It prevents the optional post-publish callback from failing after the
MQTT message has already been delivered.

The official seed deliberately contains no MQTT password. Until deployment-side
credential injection is configured, apply this local, test-only override and
request an initial full snapshot:

```powershell
docker exec moqui-database psql -U moqui -d moqui -c "UPDATE device_request SET broker_uri='paho-mqtt5:?brokerUrl=tcp://localhost:1883&qos=1&userName=artemis&password=artemis', only_changed_parameters='N' WHERE request_name='HVAC_DEMO_LiveParametersWrite';"
```

Never copy that secret-bearing URI into official seed data or a production
database.

### 6. Configure and run CODESYS

Open `moqui-plc/moqui.projectarchive`. For MQTT testing, use the local
`CODESYS Control Win V3 - x64` runtime rather than IDE Simulation: Simulation
may execute the PLC logic without creating the external MQTT socket.

In CODESYS:

1. Start `CODESYS Control Win V3 - x64`.
2. Open the PLC device **Communication Settings**, scan the local gateway and
   select the local Control Win runtime. This CODESYS Gateway connects the IDE
   to the PLC runtime; it is unrelated to `moqui-device-gateway`.
3. In the `MoquiConf` global variable list set:

   ```iecst
   brokerUrl := '127.0.0.1';
   brokerPort := 1883;
   username := "artemis";
   password := "artemis";
   liveParamsSubTopic := "moqui/hvac-demo/parameters/live";
   logTopic := "moqui-plc";
   ```

4. Leave the Recipe Manager Storage **File path** empty. This matches the
   default `deviceConfigStoragePath := '../'` convention described earlier in
   this README.
5. Under **Task Configuration**, create or verify these program calls:

   | Task | Type / interval | Priority | Program call |
   | --- | --- | --- | --- |
   | `StartTask` | Cyclic, 10 ms | 1 | `MoquiStart` |
   | `MqttParameterSubTask` | Cyclic, 1000 ms | 1 | `MqttParameterSub` |
   | `LogDispatcherTask` | Cyclic, 1000 ms | 3 | `LogDispatcher` |

   `MoquiStart` initializes the framework, loads recipes and invokes the HVAC
   `Main` FSM. `MqttParameterSub` receives and validates the approved live
   parameter keys. `LogDispatcher` sends the registered `LoggerFacade` buffers,
   including the `ParameterLogger` called by `Main` after `DeviceManager`.
   `MqttParameterPub` is not required: it is reserved for an explicitly designed
   peer-PLC parameter-replication strategy, not telemetry.
6. Disable unrelated test-suite tasks so they cannot write to the same global
   `DeviceFacade` during this demo.
7. Build the Application, choose **Online -> Login**, accept the download, and
   press **Run**.

The bottom status bar must show `RUN`, not `SIMULAT`. Useful online values are:

```text
MqttParameterSub.connectionFactory.connected = TRUE
MqttParameterSub.lastSubMessage
MqttParameterSub.parser.done / busy / error
dev.status
dev.tempSetpoint
```

With the standard `CivilCooling` recipe, `tempFeedback=26`, `tempSetpoint=22`
and `tempHysteresis=1`, so the corrected thermostat logic can leave Standby and
enter Cooling. The demo recipe completes after 30 seconds and the configuration
manager can then load the next recipe. The following Dehumidifying recipe has a
60-second total duration, including a 45-second runtime before its break; the
Heating recipe completes after another 30 seconds.

### 7. Verify a direct MQTT live update

First isolate the PLC subscription from the gateway. In another terminal send a
recognizable value:

```powershell
mosquitto_pub -h 127.0.0.1 -p 1883 -u artemis -P artemis -V mqttv5 -q 1 -t "moqui/hvac-demo/parameters/live" -m '{"parameterId":"HvacTempSetpoint","numericValue":23.25,"tempSetpoint":23.25}'
```

Expected result:

- the observer prints the JSON message;
- `MqttParameterSub.lastSubMessage` contains it;
- `dev.tempSetpoint` changes to `23.25`;
- the parser finishes without an error.

Unknown JSON keys are intentionally ignored. The executable mapper accepts
only the 20 keys modeled by `DeviceRequestItem`.

### 8. Verify gateway-to-CODESYS delivery

Set the persistent Moqui value to another recognizable number, then invoke the
modeled request through the gateway:

```powershell
docker exec moqui-database psql -U moqui -d moqui -c "UPDATE parameter SET numeric_value=23.50 WHERE parameter_id='HvacTempSetpoint';"
Invoke-RestMethod -Method Post -Uri http://localhost:8081/api/device-request/run/HVAC_DEMO_LiveParametersWrite
```

The response should contain:

```json
{"routeId":"mqtt-write-device-request","status":"completed","rowCount":20}
```

The observer should show 20 messages on the live-parameter topic and CODESYS
should show `dev.tempSetpoint=23.5`. This proves that the gateway resolved the
`DeviceRequest` and `DeviceRequestItem` rows, read the Moqui parameters and
published the generated MQTT payloads.

### 9. Verify CODESYS-to-gateway logging

Keep CODESYS in `RUN`. Normal device/application messages and the periodic
parameter snapshot appear on `moqui-plc`. A numeric snapshot entry has this
shape:

```json
{
  "loggerName":"HVAC_DEMO_PLC",
  "source":"HvacTempSetpoint",
  "type":1,
  "numericValue":23.5
}
```

The gateway applies this identity contract:

- empty `source` -> `DEVICE_LOG`, with `loggerName` as exact `Device.deviceId`;
- non-empty `source` -> `PARAMETER_LOG`, with `source` as exact
  `Parameter.parameterId`.

After one `clks.clock1minute` pulse, query PostgreSQL:

```powershell
docker exec moqui-database psql -U moqui -d moqui -c "SELECT parameter_id, numeric_value, observed_date FROM parameter_log WHERE parameter_id='HvacTempSetpoint' ORDER BY observed_date DESC LIMIT 5;"
docker exec moqui-database psql -U moqui -d moqui -c "SELECT device_id, observed_date FROM device_log WHERE device_id LIKE 'HVAC_%' ORDER BY observed_date DESC LIMIT 10;"
```

The first query should contain the value most recently observed by
`ParameterLogger`; the second confirms the device-scoped diagnostic path.

### 10. Quick troubleshooting checklist

- **No MQTT traffic:** check that `moqui-broker1` is healthy, port 1883 is not
  occupied, credentials are `artemis/artemis`, and `mosquitto_sub` was started
  before publishing.
- **Gateway health is DOWN:** verify both datasource URLs, PostgreSQL port 5432,
  `GATEWAY_DEVICE_ID=HVAC_DEMO_GATEWAY`, and that the HVAC seed was loaded.
- **REST returns zero rows:** for this isolated first-snapshot test verify that
  `only_changed_parameters='N'`. Normal production operation should update
  parameters through Moqui services and may use `onlyChangedParameters=Y`.
- **REST publishes but then fails:** the Moqui callback is probably enabled
  while the Moqui web runtime is absent; restart with
  `MQTT_WRITE_AFTERPUBLISH_ENABLED=false` for this demo only.
- **CODESYS receives nothing:** use Control Win rather than Simulation, confirm
  `brokerUrl`, `liveParamsSubTopic`, the `MqttParameterSubTask` program call and
  `connectionFactory.connected=TRUE`.
- **FSM remains in Standby:** verify that the project contains the current
  `MainRuleEngine` and that the recipe feedback is outside the thermostat band.
- **No periodic parameter rows:** `StartTask` must run every 10 ms because the
  derived clocks are based on that cycle; inspect `clks.clock1minute`, then
  `ParameterLogger.logger.error` and the `LogDispatcher` state.
- **Many text messages:** DEBUG-level FSM/device logs are expected in the demo.
  `ParameterLogger` entries are distinguished by a non-empty `source`.

To stop only the demo infrastructure:

```powershell
docker compose -f .\moqui-deploy\industrial\activemq-compose.yml -p moqui-broker down
docker compose -f .\moqui-deploy\industrial\moqui-postgres-compose.yml -p moqui down
```

Do not add `-v` unless you intentionally want to delete the persisted broker or
database volumes.

## Testing Setup

To be able to carry out automatic tests or start the framework, it is necessary to
connect the CODESYS tasks to the appropriate PLC PROGRAM.

### Pick and Place (PnP)

To run the **pick and place (pnp)** test suite, you need to link:

* `TestTripodPlanningTask` --> `TestTripodPlanning`
* `PickAndPlaceTestSuiteTask` --> `PickAndPlaceTestSuite`

### Robot Arm 6 DOF

To run the **robot arm with 6 DOF** test suite, you need to link:

* `TestRobotArmPlanningTask` --> `TestRobotArmPlanning`
* `AxisGroupTestSuiteTask` --> `AxisGroupTestSuite`

## Related components

- **[moqui-device](https://github.com/moqui/moqui-device)** — the device data model and status flows this framework generates from.
- **[moqui-math](https://github.com/moqui/moqui-math)** — the dual math model: trajectories, controllers, model lifecycle.
- **[moqui-device-gateway](https://github.com/moqui/moqui-device-gateway)** — projects the same model into Apache Camel edge routes.

## License

CC0 1.0 Universal.

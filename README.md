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
same model into field communication: Apache Camel routes in the Java gateway,
or a Rust/Tokio component inside MR-Moqui (`mr-moqui`).

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
`codesys-v3/moqui.projectarchive`, a ready-to-open CODESYS project archive that can be used
for demos, manual validation, and automated test execution.
`codesys-v4/` holds the CODESYS 4 project, generated from the canonical tree by
`scripts/convert-iec61131-to-codesys4.py` (see [codesys-v4/README.md](codesys-v4/README.md)).


## Project Structure and Platform Ports

The project is composed of the canonical IEC 61131-3 implementation and its derived platform-specific ports, alongside developer workflow utilities:

- **[iec61131](iec61131/moqui)**: The canonical source of truth for the PLC framework and runtime components, exported as a clean, vendor-neutral IEC 61131-3 reference tree.
- **[simatic-ax](simatic-ax)**: The SIMATIC AX port, generated from the canonical `iec61131` tree with AX-specific overrides.
- **[iot-firmware](iot-firmware)**: The embedded ESP32/FreeRTOS port, compiled into binary outputs, also derived from the canonical `iec61131` tree.
- **[.agents/skills](.agents/skills)**: A model-first, data-driven low-code/no-code solution for system decomposition, survey validation, Moqui XML seed rendering, HiveMind project setup, and reviewed PLC artifact generation. The skills follow the `.agents/skills/<name>/SKILL.md` layout used by `moqui/mr-moqui`.
- **[codegen](codegen)**: The code-generation workspace: resumable sessions and their generated seed data, PLC code, recipes and configuration, including the reviewed example sessions.
- **[rust-plc](rust-plc)**: The opening toward open-source ST compilers (RuSTy, IronPLC) and Rust PLC runtimes: interface declarations of the external dependencies and the compile workflow.

For details, requirements, and guides specific to each of these sub-projects, please refer to their respective documentation:
- [simatic-ax README](simatic-ax/README.md)
- [iot-firmware README](iot-firmware/README.md)
- [agent skills README](.agents/README.md)
- [codegen README](codegen/README.md)
- [rust-plc README](rust-plc/README.md)

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

- `codesys-v3/moqui.projectarchive`: the complete CODESYS project archive used for development,
  validation, demonstrations, and test execution;
- `codesys-v4`: the CODESYS 4 project, whose application is generated from the
  canonical IEC tree by `scripts/convert-iec61131-to-codesys4.py`;
- `iec61131/moqui`: the clean IEC 61131-3 export used as the vendor-neutral reference;
- `simatic-ax`: the SIMATIC AX port, generated from the canonical IEC tree with a
  limited set of manually maintained AX-specific overrides;
- `iot-firmware`: the embedded ESP32/FreeRTOS port and its supporting generated code;
- `.agents/skills`: the low-code/no-code agent skills and templates directory;
- `codegen`: the code-generation workspace (sessions and generated artifacts).
- `rust-plc`: interface declarations for compiling the canonical tree with RuSTy
  or IronPLC; the compiled output goes to `codegen/target/`.

The porting scripts must not treat a generated target as the new source of truth.
Changes are made first in the CODESYS project or canonical IEC source, then
propagated to the platform-specific ports. Files that depend on vendor libraries
or runtime-specific behavior may be preserved as explicit manual overrides.

### Vendor-neutral motion names

The CODESYS project uses the SoftMotion libraries, whose symbols carry a library
namespace (`SM3_Basic.MC_Power`, `SM3_Robotics.MC_GroupEnable`). The canonical
`iec61131/moqui` tree uses the PLCopen Motion Control names without a
qualifier (`MC_Power`, `MC_GroupEnable`). Two CODESYS reference types take their
PLCopen names: `AXIS_REF_SM3` becomes `AXIS_REF` and `AXIS_GROUP_REF_SM3`
becomes `AXES_GROUP_REF`. The remaining `SMC_*` symbols are CODESYS extensions
and keep their names.

- `scripts/export-codesys.py` strips the qualifiers on export. A qualified
  symbol that is not in the table stays qualified and is reported at the end of
  the export. `--keep-codesys-namespaces` disables the mapping.
- `scripts/codesys_namespaces.py` maps in both directions. Generated CODESYS
  applications get the qualifiers back when they copy the framework.
- Only code is mapped: comments, pragmas and string literals are left as written.

Check the canonical tree after editing it by hand:

```bash
python3 scripts/codesys_namespaces.py check iec61131
```

### Script configuration

`scripts/moqui_plc_config.py` is the shared configuration of the Python
scripts: repository paths, export defaults and the CODESYS symbol table. It is
plain Python data, not TOML, because `export-codesys.py` runs inside the
CODESYS IronPython 2.7 engine. Skill scripts under `.agents/skills` import it
from `scripts/`. It also holds the settings of `compile-st.py`: compiler
commands, external library namespaces and the files left out per target.

### Open-source ST compilers (RuSTy, IronPLC)

The canonical tree targets CODESYS. Experimental checks are available with two
open-source compilers written in Rust: [RuSTy](https://github.com/PLC-lang/rusty)
(ST to native code via LLVM) and [IronPLC](https://github.com/ironplc/ironplc)
(ST to bytecode). This is an opening for simple programs and compiler experiments. These platforms
do not currently provide the complete PLC runtime/libraries needed to run moqui-plc;
the complete framework is not supported on either target today.

**The code compiles only when every dependency is satisfied.** The CODESYS
libraries the code uses (SoftMotion, MQTT, JSON, TLS, recipes, device
diagnosis, real-time clock, Util) and the objects of the CODESYS device tree
do not exist outside CODESYS. Whoever builds the runtime has to provide them.
`rust-plc/interfaces/` declares their signatures, with no implementation and no
vendor code, so the compiler can check the moqui-plc code against them:

```bash
export MOQUI_PLC_RUSTY=~/rusty/target/release/plc
export MOQUI_PLC_RUSTY_STDLIB=~/rusty/libs/stdlib/iec61131-st
export MOQUI_PLC_IRONPLC=~/ironplc/compiler/target/release/ironplcc

python3 scripts/compile-st.py --target rusty
python3 scripts/compile-st.py --target ironplc
python3 scripts/compile-st.py --target rusty --no-interfaces   # measure the missing dependencies
```

The script copies `iec61131/` to `codegen/target/<target>/src/`, rewrites the
CODESYS dialect on the copy (`scripts/st_dialect.py`: library namespaces, global
variable list qualifiers, `UNION`, and a few compiler-specific forms), runs the
compiler, and writes `report.json` with every diagnostic tagged by origin.
`iec61131/` is never modified.

Recorded compiler measurements (RuSTy master, IronPLC 0.249; not a working PLC port):

| | without interfaces | with interfaces |
|---|---:|---:|
| RuSTy errors | 1256 | 17, all dialect differences |
| IronPLC errors | 697 | 512, mostly cascades of 23 files IronPLC cannot parse |

The compilations also surfaced points in the code itself: the `TIME` unit
(milliseconds in CODESYS, nanoseconds in RuSTy) and the integer-valued
conversion in `doubleWordToReal`/`longWordToLongReal`. See
[rust-plc/README.md](rust-plc/README.md) for the full list of rewrites,
remaining errors, findings, and what a Rust runtime has to add.

`codesys-v3/moqui.projectarchive` is a permanent repository artifact and must always be kept.
It is not a generated build directory and must not be removed during repository
cleanup.

`MoquiStart` is the entry-point orchestrator: it initializes clocks, diagnostics,
logging, input/output processing, configuration loading, and then dispatches the
application `Main` POU.

## Logging and MQTT communication

The logging follows the log4j model: each block has a `LoggerFacade` (the
logger), events go to a buffer, and one appender publishes them.

```text
LoggerFacade (control tasks)            MqttCommunication (MqttCommunicationTask, 100 ms)
  level threshold, duplicate summary       connectionFactory: connect, reconnect after mqttReconnectDelay
  -> own LogRingBuffer  ---------------->  MqttParameterSub   live parameter writes, first
     (one producer, one consumer)          MqttParameterPub   optional peer-PLC replication
                                           LogDispatcher      log batches -> MqttLogAppender -> logTopic
```

- **Buffers.** Each `LoggerFacade` owns a `LogRingBuffer` of `LOG_MAX_SIZE`
  records with one producer (the facade's task) and one consumer
  (`LogDispatcher`). Each counter has a single writer and is exchanged with the
  atomic `__XADD`, so no lock is needed and no task ever waits. A full buffer
  refuses new records and counts them; published records are never overwritten.
- **Level and repetitions.** Events below the global `logMinLevel` (`ec`,
  default `Debug`; `Info` is advisable in production) are ignored. An event equal
  to the previous one of the same facade within `defaultLogSuppressDuration`
  (10 s) is only counted and later written once with `repeatCount` = repetitions.
- **Dispatching.** `LogDispatcher` visits the sources in turn and publishes at
  most `LOG_APPENDER_BATCH_SIZE` records of one source per MQTT message, with
  QoS 1. It releases the records only after the broker acknowledged them, retries
  a failed batch with the DUP flag up to `logPublishMaxAttempts` times, and
  halves the batch while its JSON does not fit. Records refused by a full buffer
  are reported by one `Warn` record "N log events dropped". A log message
  expires on the broker after `logMessageExpiryInterval` (24 h), so the gateway
  may be offline that long without losing the logs queued for its session.
- **Connection.** `MqttCommunication` is the only caller of `connectionFactory`.
  After a connection error it disables the client, which resets it, and connects
  again after `mqttReconnectDelay`. Live parameter writes are processed before
  the log batches in every cycle.
- **Payload.** One message is the map of events read by `moqui-device-gateway`;
  the keys have a fixed width so that a reader that sorts keys keeps the order:

  ```json
  {"001":{"logEventId":"HVAC_DEMO_PLC-1798402291","logEventDate":"DT#2026-11-13-10:15:02",
          "loggerName":"HVAC_DEMO_PLC","source":"HvacTempSetpoint","level":2,"marker":0,
          "type":1,"repeatCount":1,"sequence":42,"numericValue":23.5}}
  ```

  `sequence` numbers the records of one buffer, so a reader can detect gaps.

Diagnostics: `LogSource.publishedCount`, `discardedCount` and
`reportedDropCount` in `ec.logSourceList`, `LogRingBuffer.droppedCount`,
`LogDispatcher.errorId` and `MqttCommunication.connectionErrorCount`.
`LogTestSuite` (task `LogTestSuiteTask`, without `MqttCommunicationTask`) checks
the buffer, the registration, the threshold and the repetition summary.

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

Use `codesys-v3/moqui.projectarchive` to open the full demo project directly in CODESYS.
This archive is the recommended starting point when you want to explore the
framework behavior, run the included test suites, or prepare a local demo
environment without importing the source tree manually.

## End-to-End HVAC demo

This walkthrough starts the local HVAC data path with CODESYS on Windows.
MR-Moqui framework commands use Bash on Linux/macOS or a suitable WSL environment;
configure database/broker addresses for the actual host network. It is deliberately detailed so that a first-time user can verify
the architecture without configuring physical I/O or a real PLC.

For an interactive version, invoke
`$moqui-hvac-demo-guide` from [`.agents/skills`](.agents/README.md#agent-guided-end-to-end-hvac-demo).
The agent checks prerequisites, resumes existing healthy services and requires
evidence at each checkpoint. The written procedure below remains the canonical
command reference. This guidance is for the local developer demo only, not for
production deployment.

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
- Rust/Cargo for MR-Moqui and its moqui-device-gateway component (Rust 1.99+);
- Java 21 only when using the Java Moqui framework or Java gateway;
- CODESYS Development System and `CODESYS Control Win V3 - x64`;
- Mosquitto command-line clients (`mosquitto_sub` and `mosquitto_pub`).

This guide assumes that the repositories are sibling directories:

```text
github-moqui/
  mr-moqui/             # Rust framework, master branch
  moqui-framework/      # optional Java framework
  moqui-device/
  moqui-math/
  moqui-device-gateway/
  moqui-deploy/
  moqui-plc/
```

For MR-Moqui, install `moqui-math`, `moqui-device` and `moqui-device-gateway`
under `mr-moqui/runtime/component`, all on their `mr-moqui` branch. The gateway
is a component of MR-Moqui there: it runs in the Moqui process, not as a
separate program.
`mantle-udm` is needed only for moqui-device's optional WorkEffort/Measurement
telemetry test fixture; the base suite needs no Mantle. Follow that component's
test README for the explicit fixture load and temporary test dependency.
For the Java alternative, install the corresponding Java components under
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

Wait until the container is running, then choose the framework runtime.
For **MR-Moqui master**, from its repository root in Bash:

```bash
export entity_ds_db_conf=postgres entity_ds_host=127.0.0.1 entity_ds_port=5432
export entity_ds_database=moqui entity_ds_user=moqui entity_ds_password=moqui
export entity_ds_sslmode=disable  # local demo only
./moq build --debug
./moq load --debug seed-initial
./moq load --debug seed
./moq load --debug -l runtime/component/moqui-device/data/HVACDemoGatewayData.xml
```

`HVACDemoGatewayData.xml` is demo data, not seed: it adds the broker connection
`HVAC_DEMO_MQTT` and the PLC log subscription `HVAC_DEMO_PlcLogSubscribe` used
in steps 5 to 9.

For the **Java framework alternative**, use PowerShell:

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

### 5. Start the gateway

For **MR-Moqui**, the gateway starts with Moqui. The broker credentials come
from the environment of the Moqui process (the `HVAC_DEMO_MQTT` connection reads
`MQTT_USERNAME` and `MQTT_PASSWORD`), so the model holds no password. From the
MR-Moqui root, in another terminal:

```bash
export entity_ds_db_conf=postgres entity_ds_host=127.0.0.1 entity_ds_port=5432
export entity_ds_database=moqui entity_ds_user=moqui entity_ds_password=moqui
export entity_ds_sslmode=disable  # local demo only
export MQTT_USERNAME=artemis MQTT_PASSWORD=artemis
export device_gateway_device_id=HVAC_DEMO_GATEWAY
./moq run --debug
```

`device_gateway_device_id` is the gateway this Moqui instance is: `HVAC_DEMO_GATEWAY`,
the `DgmpEdgeGateway` member of the `HVAC_DEMO` group. Within a minute of the
start, the service job `start_DeviceGatewaySubscriptions` starts the active
subscriptions of the controllers in its scope, here `HVAC_DEMO_PlcLogSubscribe`
on the `moqui-plc` topic. Requests for devices outside that scope are refused. The Moqui log reports `Device gateway subscriptions started:
1, failed: 0`; `moqui.device.gateway.SubscriptionServices.get#SubscriptionState`
(Tools app, Service Run) lists it in `activeRequestNames`. Request an initial
full live snapshot in this local demo:

```powershell
docker exec moqui-database psql -U moqui -d moqui -c "UPDATE device_request SET only_changed_parameters='N' WHERE request_name='HVAC_DEMO_LiveParametersWrite';"
```

For the **Java framework alternative**, the gateway is a separate
Java/Quarkus/Apache Camel process on the `main` branch of moqui-device-gateway:
follow the [Java gateway README](https://github.com/moqui/moqui-device-gateway/blob/main/README.md)
and the moqui-plc `master` branch, with the `HVAC_DEMO_GATEWAY` identity, the
`moqui` database, the broker above and the `moqui-plc` PLC-log topic.

### 6. Configure and run CODESYS

Open `moqui-plc/codesys-v3/moqui.projectarchive`. For MQTT testing, use the local
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
   | `MqttCommunicationTask` | Cyclic, 100 ms | 3 | `MqttCommunication` |

   `MoquiStart` initializes the framework, loads recipes and invokes the HVAC
   `Main` FSM. `MqttCommunication` owns the broker connection and calls, in this
   order, `MqttParameterSub` (receives and validates the approved live parameter
   keys), `MqttParameterPub` and `LogDispatcher` (sends the registered
   `LoggerFacade` buffers, including the `ParameterLogger` called by `Main` after
   `DeviceManager`). These three programs must not have tasks of their own.
   `MqttParameterPub` stays disabled (`paramsPubEnable = FALSE`): it is reserved
   for an explicitly designed peer-PLC parameter-replication strategy, not
   telemetry.
6. Disable unrelated test-suite tasks so they cannot write to the same global
   `DeviceFacade` during this demo.
7. Build the Application, choose **Online -> Login**, accept the download, and
   press **Run**.

The bottom status bar must show `RUN`, not `SIMULAT`. Useful online values are:

```text
connectionFactory.connected = TRUE
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

Set the persistent Moqui value to another recognizable number, then run the
modeled request:

```powershell
docker exec moqui-database psql -U moqui -d moqui -c "UPDATE parameter SET numeric_value=23.50 WHERE parameter_id='HvacTempSetpoint';"
```

Run `moqui.device.DeviceServices.run#DeviceRequest` with
`requestName = HVAC_DEMO_LiveParametersWrite` (Tools app, Service Run). The
result has `status = completed` and 20 `itemResults`, and the user gets a
"Sync Parameters completed" notification.

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
  "001":{
    "loggerName":"HVAC_DEMO_PLC",
    "source":"HvacTempSetpoint",
    "level":2,
    "type":1,
    "repeatCount":1,
    "sequence":42,
    "numericValue":23.5
  }
}
```

A message carries up to `LOG_APPENDER_BATCH_SIZE` such entries, keyed `001`,
`002`, ...; the entries also carry `logEventId`, `logEventDate` and `marker`.

`HVAC_DEMO_PlcLogSubscribe` stores these events through
`moqui.device.gateway.InboundServices.store#PlcLog` with this identity contract:

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
- **No subscription started:** check the Moqui log for `Device gateway
  subscription ... did not start` or `subscriptions are not restored`: usually
  `device_gateway_device_id=HVAC_DEMO_GATEWAY` or `MQTT_USERNAME`/`MQTT_PASSWORD`
  are missing from the Moqui environment, or `HVACDemoGatewayData.xml` was not
  loaded. `start#Subscriptions` retries a lost subscription every minute.
- **The write publishes nothing:** for this isolated first-snapshot test verify
  that `only_changed_parameters='N'`. Normal production operation should update
  parameters through Moqui services and may use `onlyChangedParameters=Y`.
- **CODESYS receives nothing:** use Control Win rather than Simulation, confirm
  `brokerUrl`, `liveParamsSubTopic`, the `MqttCommunicationTask` program call and
  `connectionFactory.connected=TRUE`. `MqttCommunication.connectionErrorCount`
  growing means the broker refuses the connection; it is retried every
  `mqttReconnectDelay`.
- **FSM remains in Standby:** verify that the project contains the current
  `MainRuleEngine` and that the recipe feedback is outside the thermostat band.
- **No periodic parameter rows:** `StartTask` must run every 10 ms because the
  derived clocks are based on that cycle; inspect `clks.clock1minute`, then
  `ParameterLogger.logger.error` and `logger.dropped`, then `LogDispatcher.errorId`
  and the `publishedCount`/`discardedCount` of the sources in `ec.logSourceList`.
- **Many text messages:** DEBUG-level FSM/device logs are expected in the demo
  (`logMinLevel = Debug`); equal consecutive messages of one block are written
  once every 10 s with their `repeatCount`. Set `logMinLevel := LogLevel.Info`
  to keep only Info and above. `ParameterLogger` entries are distinguished by a
  non-empty `source`.
- **"N log events dropped" records:** a block logs faster than the
  dispatcher publishes; raise the level threshold or `LOG_MAX_SIZE`.

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
- **[moqui-device-gateway](https://github.com/moqui/moqui-device-gateway)** — projects the same model into field communication: Apache Camel routes in the
  Java gateway (`main`), or a Rust/Tokio component that runs inside MR-Moqui (`mr-moqui`).

## License

CC0 1.0 Universal.

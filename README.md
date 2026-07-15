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

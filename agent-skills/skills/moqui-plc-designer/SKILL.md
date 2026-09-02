---
name: moqui-plc-designer
description: Use when generating or refining PLC code from Moqui automation data. This skill reads devices, parameters, device requests, status flows, and related metadata, then fills reusable templates for IOFacade, DeviceFacade, DeviceManager, DeviceDiagnostics, MainStatus, Main, and MainRuleEngine.
---

# Moqui PLC Designer

Use this skill when the task is to define or generate a data-driven automation model based on:

- Moqui XML seed data produced by `moqui-device-seed-designer`
- `moqui-device/entity/DeviceEntities.xml`
- `moqui-device/entity/DeviceViewEntities.xml`
- `moqui-device/data/DeviceData.xml`
- `moqui-math` parameter entities
- PLC skeleton patterns derived from `moqui-plc`

## What This Skill Produces

- seed-data planning for:
  - `Device`
  - `PhysicalDevice`
  - `DeviceGroup` when simple
  - `ParameterDef`
  - `Parameter`
  - `DeviceConnection`
  - `DeviceRequest`
  - `DeviceRequestItem`
  - `StatusType`
  - `StatusItem`
  - `StatusFlow`
  - `StatusFlowItem`
  - `StatusFlowTransition`
- PLC code skeletons for:
  - `MainStatus`
  - `IOFacade`
  - `DeviceFacade`
  - `DeviceManager`
  - `DeviceDiagnostics`
  - `Main`
  - `MainRuleEngine`

## Output Layout

Generate one isolated bundle for each top-level CODESYS Application. Each bundle
contains a dedicated framework copy and one runtime component that mirrors
`mantle-hvac`.

In a saved parent session, prefer:

- `output/sessions/<session-id>/generated-plc/codesys-applications/<application-id>/...`

Application layout:

- `framework/`
- `runtime/component/<component-name>/data/`
- `runtime/component/<component-name>/src/main/<namespace>/<component-name>/`
- `application-manifest.json`
- `plc-traceability.md`

Runtime component layout:

- `data/`
- `src/main/<namespace>/<component-name>/`
  - `MainStatus.dut`
  - `Main.pou`
  - `MainRuleEngine.pou`
- `src/main/org/moqui/device/`
  - `IOFacade.dut`
  - `DeviceFacade.dut`
  - `DeviceManager.pou`
  - `DeviceDiagnostics.pou`

`InputSignalUpdate.pou` and `OutputSignalUpdate.pou` remain manual and should be added later by the field engineer in `src/main/org/moqui/device/`.

CODESYS device-tree objects remain external to the Moqui seed model:

- axis references
- axis-group references
- trigger references
- motion profiles
- robotics structures

## Current V1 Scope

- seed-first via Moqui XML seed data
- `IOFacade` is auto-generable from naming conventions or `DeviceRequestItem`
- `DeviceFacade` is deterministically generable from the root `Device` plus child `Device` rows for the supported atomic moqui-plc FB types
- `DeviceManager` is deterministically generable for the supported atomic moqui-plc FB types using full-signature calls every scan
- `DeviceDiagnostics` is deterministically generable as a first blocking-device scaffold for supported atomic moqui-plc FB types
- explicit `DtMoquiPlc*` device types are preferred when present in seed data because they identify the target moqui-plc FB directly
- target convention for `DeviceManager`: always emit full-signature FB calls every scan
- for `Axis` / `AxisGroup`, placeholders in generated code are acceptable for device-tree-backed references such as `master`, `slave`, `group`, `triggerInput`, `positionProfile`, `velocityProfile`, and robotics structures
- `InputSignalUpdate` and `OutputSignalUpdate` stay manual
- `DeviceManager` and `DeviceDiagnostics` are auto-generable only when every listed device is blocking for the machine
- complex redundancy, backup, standby, or non-blocking `DeviceGroup` roles are out of scope
- `MainRuleEngine.pou` computes boolean transition requests; `Main.pou` alone consumes those requests and applies same-flow state changes
- every top-level controlled system is generated as a separate CODESYS Application with its own framework copy
- subsystem controllers execute sequentially by unique ascending `call_sequence`; `DeviceManager` executes once afterwards
- cross-flow transitions require reviewed `request_assignments` and `apply_assignments`; generation stops if either side is missing
- the repository should currently be treated as a semilavorato/base framework that each development team may further specialize

## Workflow

1. Read the seed XML and related Moqui model files.
2. Decompose the machine into subsystems and levels.
3. Identify the flat orchestration FSMs owned by systems/subsystems; introduce nesting only when required.
4. Collect or derive the physical signal catalog for `IOFacade`.
5. Collect or derive the logical parameter and device catalog for `DeviceFacade`.
6. Select or derive the `StatusFlow`.
7. Run a guided survey for each FSM state to collect the output function of `Main`.
8. Run a guided survey for each `StatusFlowTransition` to collect predicates, boolean conditions, and precedence for `MainRuleEngine`.
9. Require `outputs_reviewed: true` for every state and `code_generation_approved: true` for every FSM.
10. Generate one Application per top-level system and order its subsystem controllers by `call_sequence`.
11. Fill the PLC code templates without unresolved orchestration placeholders.
12. Cross-check the generated PLC artifacts back against the seed-derived catalog before treating them as reviewable output.

Useful helper scripts:

- `scripts/render_statusflow_templates.py`
  - generates `MainStatus`, `Main`, `MainRuleEngine`, plus base device files, from `StatusFlow`
- `scripts/render_device_catalog_from_seed.py`
  - generates `DeviceFacade`, `IOFacade`, `DeviceManager`, and `DeviceDiagnostics` from Moqui seed XML data for the supported atomic moqui-plc FB types
  - both helpers support `--session-dir` for session-aware output and status updates
- `scripts/validate_generated_plc_against_seed.py`
  - verifies that the generated PLC declarations still match the seed-derived device, parameter, request, and status-flow catalog
- `scripts/render_codesys_applications.py`
- `scripts/render_live_parameter_mapper.py`
  - resolves the approved live-parameter whitelist from the generated seed
  - writes one typed `JsonToParametersMapper` per CODESYS Application
  - generates all isolated CODESYS Application bundles from the reviewed session
  - copies the framework unless `--no-copy-framework` is used
  - validates orchestration fields and writes invocation-order traceability

Important distinction:

- `MainStatus` can be derived from `StatusFlowItem`
- `MainRuleEngine` transition topology can be derived from `StatusFlowTransition`
- the `CASE dev.status OF` body in `Main.pou` cannot be derived from `StatusFlow` alone
- for `Main.pou`, the skill must ask the user, state by state, which `PhysicalDevice` or `DeviceGroup` rows must be activated or deactivated
- for `Main.pou`, the skill must also ask which consumed transition requests may change `dev.status` in each state
- `${SENSOR_PREDICATES}` cannot be derived from `StatusFlow`; they come from process knowledge, parameter naming, thresholds, hysteresis, and safety rules collected during the workflow
- `${STATE_TRANSITION_CASES}` comes from `StatusFlowTransition` plus user-specified boolean conditions and precedence gathered during the workflow
- the output function of `Main` is the per-state block that decides which device or device-group requests are asserted while `dev.status` is in that state
- this output function can be specified in two equivalent ways:
  - direct device-level control (`enableRequest`, `disableRequest`, `enable`, `axisEnable`, `groupEnable`, ...)
  - group-level control through `DeviceGroup` / `DeviceGroupMember` when several `PhysicalDevice` rows are coordinated as one logical unit
- default request-field convention: `StatusName -> statusNameRequest`
- example: `Standstill -> standstillRequest`, `Run -> runRequest`, `ErrorStop -> errorStopRequest`
- `request-map` is only an optional override for exceptional cases
- these `Main`/`MainRuleEngine` semantics are workflow-owned and code-owned; they are not expected to be stored in Moqui entities by default

## Input Boundary

The primary input is:

- seed XML files
- XML model files
- user answers collected by the workflow

Treat `dev.` as generated IEC syntax. Seed device and parameter names must be
logical names without that prefix; add it only while rendering PLC expressions,
live-parameter assignments, and txtrecipe paths.

## Manual Boundary

The following work remains manual and belongs to the field engineer / PLC engineer:

- physical wiring review
- device-tree creation in CODESYS / Siemens AX / equivalent engineering tool
- network / fieldbus specific mapping
- `InputSignalUpdate`
- `OutputSignalUpdate`
- final binding of CODESYS device-tree objects such as axis references, axis-group references, trigger refs, motion profiles, and robotics structures
- validation against electrical schematics

## Questions To Ask

### 1. Physical catalog

- Should `IOFacade` names come from `DeviceRequestItem.requestItemName` or from naming conventions?
- Which physical signals are inputs?
- Which physical signals are outputs?
- What IEC type should be used for each physical signal?

### 2. Logical catalog

- Which analog input parameters and setpoints exist?
- Which digital parameters and boolean flags exist?
- Which atomic devices exist:
  - `Actuator`
  - `ActuatorGroup`
  - `Axis`
  - `AxisGroup`
  - `ProcessPid`
  - `SignalMgmt`
- If available, are they already typed with:
  - `DtMoquiPlcActuator`
  - `DtMoquiPlcActuatorGroup`
  - `DtMoquiPlcProcessPID`
  - `DtMoquiPlcAxis`
  - `DtMoquiPlcAxisGroup`
  - `DtMoquiPlcSignalMgmt`

### 3. FSM structure

- Which `StatusFlow` is used for the main machine?
- What is the initial state?
- Which request flags are needed for each state?
- For each state, which device/subsystem requests must be enabled or disabled?
- For each state, which incoming transition requests may change `dev.status`?
- Ask this as a survey, one state at a time.
- Example:
  - starting from `MainStatus.Standby`, which devices or device groups must activate?
  - starting from `MainStatus.Standby`, which devices or device groups must deactivate?
  - starting from `MainStatus.Standby`, which previously defined predicates allow a transition out of the state?

### 4. Predicates and transitions

- Which process/environment/safety predicates must be computed?
- Which predicates come directly from thresholds, min/max, setpoints, hysteresis, or previous-state logic?
- For each `StatusFlowTransition`, what is the boolean condition from current state to next state?
- Which transition has precedence if multiple conditions are true?
- Ask these as a guided survey, transition by transition, instead of trying to read them from the DB.

## Gotchas

- **Field-name flattening is driven by one comparison you don't see in any
  template.** `field_name_for_parameter()` (in
  `scripts/render_device_catalog_from_seed.py`) emits an unprefixed
  `dev.<parameterName>` only when `Parameter.deviceId == the --device-id you
  passed`. For every other device it emits `dev.<physicalDeviceName><Field>`
  (e.g. `dev.levelControllerSetpoint`, not `dev.setpoint`). Decide the exact
  device names in the seed survey with this in mind — renaming a device later
  renames every generated field that references it.
- **The Application/StatusFlow root is (almost) always a DeviceGroup, not a
  PhysicalDevice.** `append_statusflow_seed()` in
  `moqui-device-seed-designer/scripts/render_seed_from_surveys.py` attaches
  `statusFlowId`/`statusId` to the `DeviceGroup` device whose id matches
  `DG_<subsystem_id>`, never to the controller/PhysicalDevice row. This means
  the `--device-id` you pass to `render_device_catalog_from_seed.py` and to
  `validate_generated_plc_against_seed.py` for a single-FSM Application is
  that `DG_...` id, and both scripts need `--allow-logical-root` for it to
  validate — without the flag, `validate_seed_graph()` rejects the root for
  "no matching PhysicalDevice row" even though the seed is correct.
  `render_codesys_applications.py` already passes this flag for you; only
  standalone script invocations need to remember it.
- **A recipe (DeviceConfig/DeviceRuleSet) is not an optional nice-to-have —
  it is the only way a non-default value reaches runtime.** The base seed
  Parameter for every atomic-component field is created from the literal
  template default (`gain=1.0`, `integrationTime=0.0`, `outputMax=100.0`,
  ...), never from anything in the survey. If a tuned value (a real PID gain,
  a real setpoint) is not also carried by a `DeviceConfig` applied through a
  `DeviceRuleSet`/`DeviceRule`, the generated PLC will run with the template
  default forever, with no warning. Treat the DeviceConfig step as mandatory
  whenever any atomic-component parameter must differ from its template
  default — which is virtually always.
- **`clock := clks.clock10ms` in a generated ProcessPid `DeviceManager.pou`
  call assumes `tickTime` stays at its 10ms default.** If a recipe overrides
  `tickTime` to something else, update this line by hand to the matching
  `clks.clockXXms` symbol — the generator cannot derive it from a runtime
  recipe value, and a mismatched clock/tickTime pair breaks the internal ramp
  math silently (no compile error, no runtime error, just a setpoint ramp
  that doesn't reach the configured rate).
- **There is no way to create a standalone ParameterDef** that isn't a
  physical signal and isn't part of an atomic component's fixed field list
  (for example, a supervisory alarm threshold used only by `MainRuleEngine`).
  See `moqui-device-seed-designer`'s
  `references/free-standing-parameters.md` for the accepted workaround and
  its limits before inventing your own.

## References

Load on demand, not all at once:

- `references/plc-codegen-templates.md` — read first, before generating any
  code by hand; it explains the placeholder conventions the templates below share.
- `references/plc-codegen-templates/*.template.{dut,pou}` — the raw templates
  themselves; open only the one matching the file you're about to fill
  (e.g. `Main.template.pou` when writing `Main.pou`), not the whole set.
- `references/main-rule-engine-input-schema.md` and `.yaml` — read when
  filling `main-rule-engine-survey.yaml` (predicates/transitions), not before.
- `references/codesys-application-architecture.md` — read before running
  `render_codesys_applications.py` for the first time in a session, to
  understand the per-Application bundle layout it produces.
- `references/device-manager-full-call-signatures.md` — read when a
  `DeviceManager` FB call looks incomplete or wrong, to check the real
  full-signature contract for that FB type against `moqui-plc` source.
- `references/moqui-seed-xml-workflow.md` and `references/moqui-seed-template.xml`
  — read when hand-authoring or reviewing seed XML outside the survey scripts.
- `scripts/README.txt` — read before running any script in `scripts/` for the
  first time in a session, for the current argument list and examples.

## Output Style

- Prefer placeholder-driven generation over guessing
- Keep names aligned with Moqui entity names and PLC naming conventions
- If predicates or transitions are underspecified, stop and ask targeted questions instead of inventing logic
- Treat seed/model data as the declaration layer and generated PLC files as projections that must remain cross-checkable
- Prefer Moqui seed data in XML format when the workflow must create or update data

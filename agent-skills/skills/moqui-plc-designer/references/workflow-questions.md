# Workflow Questions

This file captures the question flow that the future skill should use while filling the PLC and Moqui templates.

## 1. System decomposition

- What is the machine or plant name?
- Into which subsystems is it decomposed?
- Which subsystem owns the main orchestration FSM?
- Which subsystems are only atomic-device collections and which are orchestrators?

## 2. Physical signal catalog for `IOFacade`

- Which `DeviceRequestItem` rows in the seed XML define the physical signal list?
- Should physical names come from `DeviceRequestItem.requestItemName` or from a naming convention?
- List all physical input signals with:
  - name
  - IEC type
  - optional physical address
- List all physical output signals with:
  - name
  - IEC type
  - optional physical address

## 3. Logical parameter and device catalog for `DeviceFacade`

- Which `Device`, `ParameterDef`, and `Parameter` rows in the seed XML define the logical model?
- List analog parameters and setpoints
- List analog limits and hysteresis values
- List digital parameters and boolean flags
- List atomic devices grouped by type:
  - `Actuator`
  - `ActuatorGroup`
  - `Axis`
  - `AxisGroup`
  - `ProcessPid`
  - `SignalMgmt`
- If the seed already uses explicit moqui-plc virtual device types, record them:
  - `DtMoquiPlcActuator`
  - `DtMoquiPlcActuatorGroup`
  - `DtMoquiPlcProcessPID`
  - `DtMoquiPlcAxis`
  - `DtMoquiPlcAxisGroup`
  - `DtMoquiPlcSignalMgmt`

## 4. FSM definition

- Which `StatusFlow` is used?
- Which ordered states should appear in `MainStatus`?
- What is the initial state?
- Which request flags are needed?
- For each state, which output requests must be asserted or cleared?
- Ask this as a survey, one state at a time:
  - starting from `MainStatus.<State>`, which `PhysicalDevice` or `DeviceGroup` rows must activate?
  - starting from `MainStatus.<State>`, which `PhysicalDevice` or `DeviceGroup` rows must deactivate?
- Are these requests defined directly on single devices:
  - `enableRequest`
  - `disableRequest`
  - `enable`
  - `axisEnable`
  - `groupEnable`
- Or are they defined at `DeviceGroup` level and then applied to multiple `PhysicalDevice` members as one logical unit?
- For each state, which consumed transition requests may move to another state?
- Keep these answers in the workflow context and render them into code; do not assume they belong in seed DB entities.

## 5. Predicate definition

- Which process predicates must be computed?
- Which environment predicates must be computed?
- Which safety predicates must be computed?
- Which predicates depend on hysteresis, timers, or previous state?
- Which predicates can be inferred from existing parameter names or limits already present in the seed data?
- Collect predicate names and meanings through the workflow survey; do not require dedicated Moqui entities for them.

## 6. Transition conditions

For every `StatusFlowTransition`:

- from status
- to status
- transition name
- activation condition
- precedence
- optional explanation comment

Generation notes:

- The transition topology can come from `StatusFlowTransition`
- The boolean expression does not come from `StatusFlowTransition` alone and must be provided by the user during the workflow survey or inferred from existing domain data
- Inspect the seed data before asking duplicate questions

## 8. Data creation

- If new Moqui data must be created, emit Moqui seed data in XML format
- Do not treat direct DB writes as the preferred workflow

## 7. Diagnostics

- Which device faults are blocking?
- Which faults should trigger `ImmediateStop`?
- Which signals are warnings only?

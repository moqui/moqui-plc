# moqui-plc knowledge

Load this reference for IEC 61131-3 generation, CODESYS layout, tasks, device
abstractions, MQTT mapping or porting. Verify current code in `iec61131`; treat
`mantle-hvac` and the relevant test suites as executable templates.

## Controller structure

`moqui-plc` is the deterministic control layer. CODESYS IEC 61131-3 is the
canonical implementation; existing scripts project it to Simatic AX and MISRA
C IoT firmware. Simatic AX currently has no MQTT projection.

Follow this call chain before generating code:

`MoquiStart` -> `DeviceConfigurationMgmt` -> component `Main` ->
`MainRuleEngine` -> `DeviceFacade`/`IOFacade` -> `DeviceManager` and diagnostics
-> input/output signal update functions.

In simulation, physical input/output calls may be commented. Do not infer that
production physical binding exists: wiring, device trees, vendor drive/network
configuration and task setup remain manual developer work.

## Application and execution semantics

Each CODESYS Application has a dedicated framework copy and runtime component.
Subsystem FSMs in one Application execute sequentially in the unique priority
order approved by the developer. The database describes their visible topology;
code performs their stitching and invocation.

`MainRuleEngine` converts numerical/process conditions into reviewed boolean
predicates and issues logical requests. `Main` and subsystem controllers own
state output functions and request consumption. The agent assists with these
semantics but does not validate whether a developer's process policy is sensible.

## Atomic components

The reusable pillars include `Axis`, `AxisGroup`, `Actuator`, `ActuatorGroup`,
`SignalMgmt` and `ProcessPid`. `Actuator` separates:

- logical Req/Ack control plane (`enableRequest`/`disableRequest`, often
  `VAR_IN_OUT`);
- physical data plane (`enable`/`disable`, feedback sensors, fault, reference
  and feedback values).

This supports contactor-driven bistable loads and intelligent drives. Control/
status words may be mapped into Actuator signals, while drive-internal PID and
safety remain in the drive. Functional safety, STO, safety relays/PLCs and
redundancy mechanisms are outside the framework.

## MQTT programs and mappings

- `LogDispatcher` publishes numeric/text logger batches.
- `MqttParameterSub` receives approved live parameter updates.
- `MqttParameterPub` is a separate scheduled program for outbound parameters.
- `JsonToParametersMapper` is intentionally documentation/no-op in the generic
  template; generate a reviewed Application-specific whitelist mapper.
- `ParametersToJsonMapper` contains the selected outbound projection.

MQTT keys are the reviewed DeviceRequestItem names. Add `dev.` only inside IEC
access expressions. Recipe/live parameters exclude actual and feedback values.

## Generation rules

- Generate faithfully from current `mantle-hvac` structure and existing
  axis/group suites; do not synthesize a different PLC architecture.
- Preserve code authority for predicates, output functions, interlocks and call
  order rather than forcing them into Moqui entities.
- Generate tests only when the developer requests them. Source merging and
  commissioning remain developer-owned.
- Treat `DeviceFacade` as logical equipment/config state and `IOFacade` as the
  physical mapping boundary.

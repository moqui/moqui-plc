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

- `LogDispatcher` publishes numeric/text logger batches and is the operational
  telemetry path.
- `MqttParameterSub` receives approved live parameter updates.
- `MqttParameterPub` is an optional peer-PLC/Application parameter exchange for
  a developer-defined redundancy strategy; it is not the telemetry path.
- `JsonToParametersMapper` is the executable Application-specific inbound
  whitelist generated from reviewed DeviceRequestItems. Unknown envelope keys
  remain non-blocking and are ignored.
- `ParametersToJsonMapper` is a documentation-only template unless the
  Application explicitly requires parameter replication for redundancy. Keep
  `MqttParameterPub` disabled by default and never reuse the inbound live-write
  whitelist there.
- Physical input/output signal logging belongs to `InputSignalUpdate` and
  `OutputSignalUpdate`. Application logical numeric values belong to a generated
  `ParameterLogger`, invoked after `DeviceManager` so it observes a coherent
  post-update snapshot.
- A PLC task may run every 10 ms while `ParameterLogger` gates snapshots with
  the generated `Clocks` pulses (for example `clock1minute`). A
  `DeviceRequest.pollingInterval` may specify the desired model-side cadence,
  but the generator must materialize that cadence in IEC code; the PLC does not
  read the Moqui entity dynamically.
- `LogEvent` already carries the persistent identity convention: `loggerName`
  is the exact owning `Device.deviceId`; an empty `source` denotes a
  device-scoped event, while a non-empty `source` is the exact pre-existing
  `Parameter.parameterId`. Payload type (numeric, text or enum) is independent
  from this scope. Never concatenate logger fields or use descriptive
  device/parameter names as database keys.
- Keep the manual Simatic AX and IoT firmware projections aligned with this
  identity convention. IoT `ParameterLogger` snapshots may span multiple MQTT
  batches, so the ring drain must retain entries not included in the current
  batch rather than clearing the whole buffer.

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

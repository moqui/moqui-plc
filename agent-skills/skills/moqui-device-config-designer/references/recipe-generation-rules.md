# Recipe Generation Rules

## Purpose

This skill generates recipe templates like:

- `*.HvacDeviceConfig.txtrecipe`
- `*.DeviceConfig.txtrecipe`

Each line is an assignment in the form:

```text
dev.somePath:=someValue
```

## Source of truth

The recipe template is derived primarily from `DeviceFacade` in:

- [moqui/moqui-plc](https://github.com/moqui/moqui-plc)

The seed XML can be used secondarily to:

- identify the machine/device list
- identify `deviceTypeEnumId`
- inspect existing naming conventions

But the actual recipe field list should come from the PLC-side `DeviceFacade`, because that is where the real instantiated FB structure is declared in `moqui/moqui-plc`.

Include:

- every eligible top-level variable declared directly in `DeviceFacade`
- every eligible field of each instantiated FB declared in `DeviceFacade`
- example values suitable as placeholders or starter commissioning values

Selection rule:

- include all and only fields that correspond to recipe-suitable `VAR_INPUT`
  values of the underlying moqui-plc FB
- exclude any `VAR_IN_OUT`
- exclude any `VAR_INPUT` that is actually bound to physical I/O signals
- if the FB exposes control-like inputs such as `enable`, `execute`, or
  similar, use conservative defaults so the machine stays `OFF` / `Standby`
  when a recipe is loaded
- for enum-like fields, emit the numeric constant value expected by the PLC

## Included categories

### Simple parameters

- analog setpoints
- min/max limits
- hysteresis values
- operating-mode booleans
- timing values

### FB parameters

For each declared FB instance, include every field from the fixed allowed list
for that FB type whenever that field is part of the `DeviceFacade` surface.

Examples:

- `Actuator`
  - `actuatorId`
  - `actuatorName`
  - `actuationType`
  - `feedbackType`
  - `model`
  - `operationType`
  - `enableTime`
  - `disableTime`
  - `enablePreset`
  - `diagnosticsEnable`

- `ProcessPid`
  - `controlSystemId`
  - `controlSystemName`
  - `feedbackMultiplier`
  - `setpoint`
  - `setpointMultiplier`
  - `setpointRampType`
  - `setpointIncreaseTime`
  - `setpointDecreaseTime`
  - `setpointFreezeEnable`
  - `deviationInversion`
  - `gain`
  - `integrationTime`
  - `derivationTime`
  - `setpointMin`
  - `setpointMax`
  - `outputMin`
  - `outputMax`
  - `outputFreezeEnable`
  - `offset`
  - `deadbandRange`
  - `deadbandDelay`
  - `sleepLevel`
  - `sleepDelay`
  - `wakeupDeviation`
  - `wakeupDelay`
  - `sleepBoostLevel`
  - `sleepBoostTime`
  - `trackingMode`
  - `trackingRef`
  - `tickTime`
  - `setpointEpsilon`

- `ActuatorGroup`
  - `actuatorGroupId`
  - `actuatorGroupName`
  - `actuatorNum`
  - `minRunning`
  - `maxRunning`
  - `demandSetpoint`
  - `startDelay`
  - `stopDelay`
  - `autochange`
  - `autochangeInterval`
  - `maxWearImbalance`
  - `autochangeLevel`
  - `autochangeTrigger`

- `Axis`
  - `cmd`
  - `position`
  - `distance`
  - `velocity`
  - `velocityDiff`
  - `acceleration`
  - `deceleration`
  - `jerk`
  - `bufferMode`
  - `direction`
  - `homePosition`
  - `ratioNumerator`
  - `ratioDenominator`
  - `masterSyncPos`
  - `slaveSyncPos`
  - `camVersion`
  - `masterOffset`
  - `slaveOffset`
  - `phaseShift`
  - `setPositionMode`
  - `overrideEnable`
  - `velFactor`
  - `accFactor`
  - `jerkFactor`
  - `jogForward`
  - `jogBackward`
  - `touchProbeWindow`
  - `touchProbeFirst`
  - `touchProbeLast`

- `AxisGroup`
  - `axisGroupId`
  - `axisGroupName`
  - `cmd`
  - `velocity`
  - `acceleration`
  - `deceleration`
  - `jerk`
  - `transitionParameter`
  - `overrideEnable`
  - `velFactor`
  - `accFactor`
  - `jerkFactor`

## Exclusions

By default exclude:

- feedback fields such as `*Feedback`
- transient runtime fields
- computed predicates
- request flags
- current FSM status
- any parameter that should be classified in Moqui as `purposeEnumId = PpFeedback`
- any field coming from physical I/O wiring even if it appears as `VAR_INPUT`

## Ordering

Recommended order:

1. top-level simple parameters
2. top-level timing and mode flags
3. FB instances grouped by instance name

## Moqui data creation

When the workflow must create new `ParameterDef` or `Parameter` data, prefer Moqui seed XML.

Do not use direct database writes as the primary authoring workflow.

## Helper script

See:

- `../scripts/render_recipe_candidates.py`

This script generates candidate recipe-template lines directly from `DeviceFacade.dut`.

## Practical simplification

For this repository, it is enough to treat a recipe as a flat list of assignments:

```text
dev.path:=value
```

The template does not need to encode full commissioning knowledge.
It only needs to show the expected assignment format and the configurable paths exposed by `DeviceFacade`.

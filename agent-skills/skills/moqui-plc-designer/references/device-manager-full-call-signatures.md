# DeviceManager Full Call Signatures

This reference defines the generation rule for `DeviceManager`:

- each PLC FB should be called every scan with its full signature
- no partial FB calls should be emitted
- if a parameter is semantically unchanged, it is still passed again
- scan-based repetition is preferred to special-casing

## Why this rule is preferred

- simpler templates
- fewer conditional branches in the generator
- easier comparison with reference PLC code
- every field required by the FB signature must exist in `DeviceFacade`
- the remaining work becomes deterministic wiring

## Boundary with the CODESYS device tree

The following values are not expected to come from Moqui seed data:

- axis references such as `slave`
- axis-group references such as `group`
- synchronization references such as `master`
- trigger references such as `triggerInput`
- motion profiles such as `positionProfile`, `velocityProfile`, `accelerationProfile`
- robotics structures such as `SMC_POS_REF`

The generator should still emit these parameters in the PLC code, using declared facade fields and placeholders where needed.
If the generated project does not compile in CODESYS before those objects are bound, that is acceptable and expected.

## Source files

Derive the full signatures from the real FB declarations in:

- [moqui/moqui-plc](https://github.com/moqui/moqui-plc)
- `iec61131/moqui/framework/src/main/org/moqui/device/Actuator.pou`
- `iec61131/moqui/framework/src/main/org/moqui/device/ActuatorGroup.pou`
- `iec61131/moqui/framework/src/main/org/moqui/device/ProcessPid.pou`
- `iec61131/moqui/framework/src/main/org/moqui/motion/Axis.pou`
- `iec61131/moqui/framework/src/main/org/moqui/motion/AxisGroup.pou`
- `iec61131/moqui/framework/src/main/org/moqui/diagnostics/SignalMgmt.pou`

## Actuator

- handshake:
  - `enableRequest`
  - `disableRequest`
- metadata:
  - `actuatorId`
  - `actuatorName`
  - `actuationType`
  - `feedbackType`
  - `model`
  - `operationType`
- timing / diagnostics:
  - `clock`
  - `enableTime`
  - `disableTime`
  - `enablePreset`
  - `diagnosticsEnable`
- feedback / optional process values:
  - `enabledSensor`
  - `disabledSensor`
  - `externalFault`
  - `ref`
  - `feedback`

## ActuatorGroup

- handshake arrays:
  - `enableRequests`
  - `disableRequests`
- metadata:
  - `actuatorGroupId`
  - `actuatorGroupName`
- topology:
  - `actuatorNum`
  - `minRunning`
  - `maxRunning`
- demand logic:
  - `demandSetpoint`
  - `startPoints`
  - `stopPoints`
  - `startDelay`
  - `stopDelay`
- autochange:
  - `autochange`
  - `autochangeInterval`
  - `maxWearImbalance`
  - `autochangeLevel`
  - `autochangeTrigger`
- feedback arrays:
  - `actuatorEnabled`
  - `actuatorFault`
  - `actuatorInterlocked`
  - `runHours`
- commands:
  - `groupEnable`
  - `groupDisable`

## ProcessPid

- control gate:
  - `enable`
  - `reset`
- metadata:
  - `controlSystemId`
  - `controlSystemName`
- process values:
  - `feedback`
  - `feedbackMultiplier`
  - `setpoint`
  - `atSetpointHysteresis`
  - `setpointMultiplier`
  - `setpointMin`
  - `setpointMax`
- ramp / shaping:
  - `setpointRampType`
  - `setpointIncreaseTime`
  - `setpointDecreaseTime`
  - `setpointFreezeEnable`
- control polarity / output limits:
  - `deviationInversion`
  - `outputMin`
  - `outputMax`
- plus the remaining declared PID inputs from the FB

## Axis

- `VAR_IN_OUT`:
  - `axisEnable`
  - `slave`
- command:
  - `cmd`
- motion parameters:
  - `position`
  - `distance`
  - `velocity`
  - `velocityDiff`
  - `acceleration`
  - `deceleration`
  - `jerk`
  - `bufferMode`
  - `direction`
- synchronization / homing / references:
  - `homePosition`
  - `master`
  - `triggerInput`
  - `positionProfile`
  - `velocityProfile`
  - `accelerationProfile`
  - `ratioNumerator`
  - `ratioDenominator`
  - `masterSyncPos`
  - `slaveSyncPos`
  - `camId`
  - `camVersion`
  - `startMode`
  - `masterOffset`
  - `slaveOffset`
  - `phaseShift`
  - `setPositionMode`
- override / jog / reset / parameter access:
  - `overrideEnable`
  - `velFactor`
  - `accFactor`
  - `jerkFactor`
  - `jogForward`
  - `jogBackward`
  - `reset`
  - `parameterNumber`
  - `parameterValue`
  - `parameterBoolValue`
  - `touchProbeWindow`
  - `touchProbeFirst`
  - `touchProbeLast`

## AxisGroup

- `VAR_IN_OUT`:
  - `group`
  - `groupEnable`
- metadata:
  - `axisGroupId`
  - `axisGroupName`
- command:
  - `cmd`
- position targets:
  - `endPoint`
  - `auxPoint`
- circular / path controls:
  - `circMode`
  - `pathChoice`
- dynamics:
  - `velocity`
  - `acceleration`
  - `deceleration`
  - `jerk`
- coordinate / transition:
  - `coordinateSystem`
  - `bufferMode`
  - `transitionMode`
  - `transitionParameter`
- override / reset:
  - `overrideEnable`
  - `velFactor`
  - `accFactor`
  - `jerkFactor`
  - `reset`

## SignalMgmt

- `operationType`
- `code`
- `category`
- `resetPol`
- `outputAction`
- `activationCondition`
- `autoResetCondition`
- `reset`
- `auxReset`
- `selectiveResetTrigger`
- `selectiveResetCode`
- `loggerName`

## Generation consequence

`DeviceManager` generation for the supported atomic moqui-plc FB types should
now be treated as deterministic:

- kind inference
- full signature mapping
- deterministic field naming
- deterministic call rendering
- explicit placeholders for CODESYS device-tree integrations that are outside the Moqui seed model

The unstable part of the overall PLC generator is no longer `DeviceManager`,
but the behavior layer (`Main` and `MainRuleEngine`), which remains pending
real test cases.

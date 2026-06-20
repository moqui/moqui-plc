# Seed Survey Fields

This reference lists the main information blocks that the seed workflow should collect.

## Upstream Engineering Preconditions

Before seed authoring starts, the workflow should already have collected:

- the hierarchical system decomposition down to elementary devices
- the logical model and actuation/feedback classification of each elementary device
- the naming rules and normalized list of physical input/output signals
- the grouping of devices/signals by natural frequency or sampling domain

These upstream data blocks are not optional context. They are the best source
of:

- completeness constraints
- expected physical signals
- expected logical device models
- guided follow-up questions
- detection of underspecified user requirements

The seed workflow should therefore treat missing upstream engineering data as a
reason to pause and ask targeted questions instead of filling gaps by guesswork.

## System decomposition

- `subsystemId`
- optional `parentSubsystemId`
- `subsystemName`
- `subsystemType`
- optional `controlResponsibility`
- optional `candidateStatusFlowId`
- optional `notes`

## Elementary device classification

For each elementary device:

- `deviceId`
- parent subsystem reference
- logical model:
  - `Actuator`
  - `ActuatorGroup`
  - `ProcessPid`
  - `Axis`
  - `AxisGroup`
  - `SignalMgmt`
  - or another explicit model
- actuation/feedback class:
  - `DA-DF`
  - `SA-DF`
  - `SA-SAFD`
  - `SA-SDFD`
  - `SA-NO`
- expected actuation signals
- expected feedback signals
- positive/negative logic rule
- notes and open questions

## Signal catalog and naming rules

- default positive logic policy
- signal naming convention
- prefixes/suffixes by direction or signal family
- one row per normalized physical signal:
  - `signalId`
  - `deviceId`
  - `direction`
  - `signalKind`
  - `iecType`
  - optional `reverseLogic`
  - source classification rule
  - notes

## Sampling domains

- `domainId`
- `domainName`
- natural-frequency class
- scan/poll interval
- transport scope
- assigned devices
- assigned signals

These domains should drive the automatic partitioning of generated
`DeviceRequest` rows for monitoring and control.

## Live parameters

Optional whitelist of logical parameters admitted to live runtime changes
through `MqttParameterSub`:

- `parameterId`
- `deviceId`
- `parameterName`
- `iecType`
- `mqttKey`
- optional notes

The point is not to ask the user which FB parameters exist in theory. Those are
mostly fixed by the modeled component (`Actuator`, `ProcessPid`, `Axis`,
`SignalMgmt`, ...). The user should only identify which of them may be changed
live in the application context.

## Gateway topology

Optional but strongly recommended when the application also uses
`moqui-device-gateway`:

- `gatewayDeviceId`
- `gatewayName`
- optional `gatewayDeviceTypeEnumId`
- optional `gatewayMemberPurposeEnumId`
- `scopedSubsystemIds`
- optional `scopedDeviceIds`
- optional notes

This survey is the data source for gateway identity and gateway scope. It
should drive the generation of:

- gateway `Device`
- gateway `PhysicalDevice`
- gateway `DeviceGroupMember`
- startup-scope checks and commissioning guidance

Canonical defaults currently assumed by the generators:

- gateway `deviceTypeEnumId = DtEdgeGateway`
- subsystem group `deviceTypeEnumId = DgtSubsystem`
- child subsystem member `purposeEnumId = DgmpSubsystem`
- elementary device member `purposeEnumId = DgmpControlledDevice`
- root PLC member `purposeEnumId = DgmpProcessPLC`

## Transport architecture

Required before declaring the seed complete:

- `primaryTransportMode`
  - `gateway`
  - `plc4j`
  - `hybrid`
- `allowsHybridProjection`
- gateway projection required yes/no
- plc4j projection required yes/no
- default PLC4J `runServiceName`
- connection strategy notes
- rationale / constraints

This survey is where the workflow captures the non-optional fact that the
model must project onto at least one runtime transport layer:

- `moqui-device-gateway`
- `moqui-plc4j`
- or both

## Device / PhysicalDevice

- `deviceId`
- optional `parentDeviceId`
- `deviceTypeEnumId`
- optional `purposeEnumId`
- optional `controlMethodEnumId`
- optional `operatingModeEnumId`
- optional `statusTypeId`
- `statusFlowId`
- `statusId`
- optional `configId`
- optional `description`
- optional `location`
- `deviceName`
- optional `version`
- optional `hardwareVersion`
- optional `firmwareVersion`
- optional `operatingSystem`
- optional `softwareApplication`
- optional `cycleTime`
- optional `isMulticore`

## DeviceGroup / DeviceGroupMember

- `deviceId`
- `groupName`
- optional group `purposeEnumId`
- optional group `statusFlowId`
- optional group `statusId`
- optional group `description`

For each `DeviceGroupMember`:

- `deviceId`
- `memberDeviceId`
- optional but recommended `purposeEnumId`
- `sequenceNum`
- optional `description`
- optional `statusFlowId`
- optional `statusId`

## ParameterDef

- `parameterDefId`
- `parameterTypeEnumId`
- `purposeEnumId`
- `parameterCode`
- `parameterName`
- `description`
- optional limits/defaults

## Parameter

- `parameterId`
- `deviceId`
- `parameterDefId`
- optional `parameterAlias`
- optional `sequenceNum`
- value field:
  - `numericValue`
  - or `symbolicValue`
  - or `parameterEnumId`

## DeviceConnection

- `connectionName`
- `deviceId`
- optional `connectionTypeEnumId`
- optional `purposeEnumId`
- optional `description`
- optional `userId`
- `driverEnumId`
- optional `transportEnumId`
- optional `transportConfig`
- optional `options`

## DeviceRequest

For `moqui-plc` based systems, request design should normally be reduced to a
small standard set:

- framework `ec` read/write request family
- recipe export request
- one live-parameter MQTT request whose variability is mostly in
  `DeviceRequestItem`

Before creating extra `DeviceRequest` rows, the workflow should ask whether the
need can already be covered by one of these standard families.

- `requestName`
- optional `parentRequestName`
- `deviceId`
- `requestTypeEnumId`
- `purposeEnumId`
- optional `requestGroup`
- optional `priority`
- optional `sequenceNum`
- optional `description`
- `routerEnumId`
- optional `connectionName`
- optional `runServiceName`
- optional `onlyChangedParameters`
- optional `brokerUri`
- optional `pollingInterval`
- optional `timeout`
- optional `qos`
- optional `retained`
- optional `query`

## DeviceRequestItem

- `requestName`
- `parameterId`
- `sequenceNum`
- optional `requestItemName`
- optional `query`
- `itemTypeEnumId`
- optional `minItemValue`
- optional `maxItemValue`
- optional `defaultItemValue`
- optional `itemValue`
- optional `itemUomId`
- optional `allowDuplicate`
- optional `tolerance`
- optional `scalingFactor`
- optional `offsetValue`
- optional `significantDigits`
- optional `reverseLogic`
- optional `activationDelay`

DeviceRequestItem rows should be cross-checked against the signal catalog:

- every exported PLC-side physical signal should have a modeled source rule
- direction should agree with the logical control surface
- reverse logic should be explicit in data rather than hidden in later code
- requests should preferably be partitioned by sampling / timing domain instead
  of being emitted as one undifferentiated monitoring list

## Standard moqui-plc framework surface

When the target PLC uses `moqui-plc` as its framework, the survey should also consider the standard
framework-facing variables exposed in `ec.gvl`, including:

- `enable`
- `init`
- `fault`
- `error`
- `commError`
- `reset`
- `autoReset`
- `allConfigLoaded`
- `retryCount`
- `retryTime`
- `isPrimary`
- `heartbeat`
- `logAppenderEnable`
- `paramsPubEnable`
- `paramsSubEnable`

## StatusFlow

- `statusTypeId`
- `statusFlowId`
- ordered `StatusItem`
- initial state
- ordered `StatusFlowTransition`

## DeviceConfig / DeviceConfigSet / DeviceRuleSet / DeviceRule

Semantics:

- `DeviceConfig` is a reusable template compatible with one `deviceTypeEnumId`
- `DeviceConfigSet` is the analogous reusable template container for a device group
- `Parameter.deviceConfigId` holds the parameter instances of that template
- the first generated config should normally be a `TEMPLATE`
- `DeviceRule` applies or asserts one config on one logical `Device`, which may
  correspond either to a `PhysicalDevice` or to a `DeviceGroup`
- `DeviceRuleSet` sequences multiple rules

For `DeviceConfig`:

- `deviceConfigId`
- optional `parentConfigId`
- optional `configTypeEnumId`
- optional `purposeEnumId`
- `deviceTypeEnumId`
- `configName`
- optional `description`
- optional `controlMethodEnumId`
- optional `approximatedFunctionId`

For `DeviceConfigSet`:

- `deviceConfigId`
- `configSetName`
- optional but recommended parent `DeviceConfig.deviceTypeEnumId` consistency note
- one or more `DeviceConfigSetMember`

For each `DeviceConfigSetMember`:

- `deviceConfigId`
- `memberConfigId`
- optional `sequenceNum`
- optional `description`

Recipe-loading compatibility questions:

- which `deviceTypeEnumId` does each `DeviceConfig` target?
- which `DeviceGroup` does each `DeviceConfigSet` represent?
- for each `DeviceRule`, does `Device.deviceTypeEnumId` match the bound
  `DeviceConfig.deviceTypeEnumId`?
- for each `DeviceRuleSet`, what is the intended processing priority order?

For `DeviceRuleSet`:

- `deviceRuleSetId`
- optional `parentRuleSetId`
- optional `purposeEnumId`
- optional `sequenceNum`
- `ruleSetName`
- optional `description`

For `DeviceRule`:

- `deviceRuleId`
- optional `parentRuleId`
- `ruleTypeEnumId`
- `deviceRuleSetId`
- `deviceConfigId`
- `deviceId`
- optional `statusId`
- optional `statusFlowId`
- `ruleName`
- `priority`
- optional `description`
- optional `serviceName`
- optional `isEnabled`
- optional `runDevice`
- optional `floatingPointTolerance`
- optional `timeTolerance`

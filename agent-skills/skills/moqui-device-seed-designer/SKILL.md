---
name: moqui-device-seed-designer
description: Use when creating or validating Moqui seed XML for devices, parameters, parameter definitions, device requests, device request items, and status flows. This skill runs a survey-style workflow, accepts structured user input or imported files, checks completeness against Moqui entity models, and emits seed data ready for review before optional copy into a Moqui component.
---

# Moqui Device Seed Designer

Use this skill when the task is to collect, validate, and generate Moqui seed data for a specific machine, plant, or PLC automation application.

## Goal

Produce `entity-facade-xml` seed files for:

- `Device`
- `PhysicalDevice`
- `DeviceGroup` when simple
- `DeviceGroupMember` when simple
- `ParameterDef`
- `Parameter`
- `DeviceConnection`
- `DeviceRequest`
- `DeviceRequestItem`
- `DeviceConfig`
- `DeviceConfigSet`
- `DeviceConfigSetMember`
- `DeviceRuleSet`
- `DeviceRule`
- `StatusType`
- `StatusItem`
- `StatusFlow`
- `StatusFlowItem`
- `StatusFlowTransition`

## Input Modes

The skill should accept data from any decent user format, including:

- interactive question flow
- CSV
- Excel exports
- text/markdown tables
- Word documents or copied specs when they are structured enough

The skill should normalize the data internally and detect what is still missing.

## Workflow

1. Read the entity models from:
   - `moqui-device/entity/DeviceEntities.xml`
   - `moqui-device/entity/DeviceViewEntities.xml`
   - `moqui-math/entity/MathEntities.xml`
2. Ask only for the data that is still missing or ambiguous.
3. Validate that all essential fields for the requested entities are present.
4. Generate Moqui seed XML for review.
5. In a saved plant session, write the reviewed seed into `seed-data/`.
6. After user approval, optionally copy the generated seed file into the target Moqui component path.

Useful helper scripts:

- `scripts/render_seed_bundle.py`
  - composes a final seed XML from reusable fragments such as `base`, `mqtt`, `gateway_wrapper`, and `framework_ec`
  - also supports `opcua` as an auxiliary direct-transport reference fragment when needed
  - in a session workflow, prefer `--session-dir` so the seed is written under the session workspace and `session.json` is updated
- `scripts/render_seed_from_surveys.py`
  - validates multi-FSM surveys and materializes StatusType/StatusItem/StatusFlow topology
  - assigns each FSM to its owning subsystem Device and preserves the physical device parent tree
  - generates executable gateway-side MQTT/OPC UA requests plus their Moqui-side REST dispatch wrappers

## Validation Principle

The entity definitions are the guide for completeness checks.

The skill should verify:

- required identifiers are present
- parent/child references are resolvable
- enumerations and purpose fields are coherent
- request items point to existing parameters
- each gateway sampling domain resolves to exactly one declared gateway transport
- MQTT requests define a Camel `paho-mqtt5:` base URI and explicit topics
- OPC UA requests reference a generated `DeviceConnection` and explicit node IDs
- each Moqui-side dispatch wrapper targets a gateway Device and references its field-side request by `query`
- status flows contain ordered states and valid transitions
- every system/subsystem owns at most one directly visible FSM Device projection
- flat FSMs remain independent; nested transitions use `toStatusFlowId` only when explicitly requested
- `conditionExpression` remains empty because transition conditions are code-owned
- the seed can serve downstream skills such as `moqui-plc-designer`

## Standard DeviceRequest Philosophy

For `moqui-plc` based systems, the standard `DeviceRequest` families should stay
very small.

The primary modelling effort belongs to:

- `Device`
- `PhysicalDevice`
- `DeviceGroup`
- `DeviceGroupMember`
- `ParameterDef`
- `Parameter`
- `DeviceConfig`
- `DeviceConfigSet`
- `DeviceConfigSetMember`
- `DeviceRuleSet`
- `DeviceRule`

The standard request families are normally only:

1. framework `ec` read/write requests
2. recipe export request
3. one live-parameter request for values acquired by `MqttParameterSub` in [moqui/moqui-plc](https://github.com/moqui/moqui-plc)

For each gateway-executed family, keep the two model rows distinct:

- the field-side request targets the PLC and contains MQTT/OPC UA transport data;
- the Moqui-side wrapper targets the gateway, uses
  `moqui.device.DeviceGatewayServices.run#GatewayDeviceRequest`, stores the
  gateway REST base URL in `brokerUri`, and names the field-side request in
  `query`.

Do not put API keys, broker passwords, or OPC UA credentials in generated seed
files. Supply credentials through deployment configuration or referenced user
accounts.

So the skill should avoid over-designing many different request families when
the real variability belongs to the parameter model and to the request items.

## Standard Recipe-Loading Flow

For recipe-oriented authoring, the workflow should explicitly cover:

1. `DeviceConfig`
   - reusable config template for one `deviceTypeEnumId`
   - compatible with any `Device` of the same `deviceTypeEnumId`
2. `DeviceConfigSet`
   - reusable config-set template for one `DeviceGroup`
   - a set of member `DeviceConfig` rows grouped through `DeviceConfigSetMember`
3. `DeviceRuleSet`
   - ordered sequence of `DeviceRule`
4. `DeviceRule`
   - binds one `DeviceConfig` to one specific logical `Device`
   - compatibility rule:
     - `DeviceRule.deviceId` must point to a `Device` whose `deviceTypeEnumId`
       matches the `DeviceConfig.deviceTypeEnumId`

This means:

- `DeviceConfig` is type-level
- `DeviceRule` is instance-level
- `DeviceConfigSet` is the group-level analogue of `DeviceConfig`
- `DeviceRuleSet` sequences the actual application or validation rules

For atomic-device `DeviceConfig` templates, derive the field list from the
underlying `moqui-plc` FB code:

- include all and only the recipe-suitable `VAR_INPUT` fields
- exclude every `VAR_IN_OUT`
- exclude `VAR_INPUT` fields that are really tied to physical I/O
- when control-like inputs such as `enable` or `execute` are part of the fixed
  catalog, use conservative defaults so recipe loading keeps devices stopped or
  in standby
- for enums, store the numeric constant value expected by the PLC

## Output Style

- emit `entity-facade-xml` seed files
- in a parent session workflow, prefer `output/sessions/<session-id>/seed-data/`
- keep stable ordering
- group rows by entity type in a readable way
- preserve references and naming conventions already present in Moqui
- stop and ask targeted follow-up questions if required data is missing

## References

- `references/seed-survey-fields.md`
- `references/seed-output-workflow.md`
- `references/atomic-component-library.json`
- `references/use-cases/mantle-hvac-reverse-engineering.md`
- `references/mantle-hvac-like-seed-example.xml`
- `references/seed-bundle-spec.example.json`
- `references/base-device-seed-template.xml`
- `references/digital-sensor-seed-template.xml`
- `references/analog-sensor-seed-template.xml`
- `references/actuator-seed-template.xml`
- `references/actuator-group-seed-template.xml`
- `references/process-pid-seed-template.xml`
- `references/axis-seed-template.xml`
- `references/axis-group-seed-template.xml`
- `references/signal-mgmt-seed-template.xml`
- `references/device-group-seed-template.xml`
- `references/device-config-semantics.md`
- `references/device-config-load-workflow.md`
- `references/device-config-template.xml`
- `references/device-config-set-template.xml`
- `references/actuator-device-config-template.xml`
- `references/actuator-group-device-config-template.xml`
- `references/process-pid-device-config-template.xml`
- `references/axis-device-config-template.xml`
- `references/axis-group-device-config-template.xml`
- `references/signal-mgmt-device-config-template.xml`
- `references/mqtt-device-request-seed-template.xml`
- `references/opcua-device-request-seed-template.xml`
- `references/gateway-wrapper-request-seed-template.xml`
- `references/framework-ec-seed-template.xml`
- `references/framework-ec-requests.md`

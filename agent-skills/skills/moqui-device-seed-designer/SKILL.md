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
- `DeviceGroup` from an explicit developer-approved survey
- `DeviceGroupMember` from an explicit developer-approved survey
- `ParameterDef`
- `Parameter`
- `DeviceConnection`
- `DeviceRequest`
- `DeviceRequestItem`
- `DeviceConfig`
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
  - emits one `PhysicalDevice` per hardware CPU or CODESYS Application
  - requires explicit DeviceGroup membership and final approval gates (or `--draft`)
  - composes atomic `DeviceConfig` records through ordered `DeviceRuleSet`/`DeviceRule` rows

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
- `PhysicalDevice.deviceName`, `ParameterDef.parameterName`, and
  `Parameter.parameterAlias` contain domain names only and never a leading
  `dev.`; IEC namespace prefixes belong to downstream PLC projections

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
- `DeviceRuleSet`
- `DeviceRule`

The standard request families are normally only:

1. framework `ec` read/write requests
2. recipe export request
3. one live-parameter request for values acquired by `MqttParameterSub` in [moqui/moqui-plc](https://github.com/moqui/moqui-plc)

The live request is a whitelist over existing device-bound Parameters. Ask only
which parameters may be changed and their JSON keys; do not create duplicate
Parameter/ParameterDef rows. The PLC designer generates the corresponding
Application-specific mapper.

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
2. `DeviceRuleSet`
   - composition boundary rooted at one Device or DeviceGroup
   - orders all atomic configuration operations by `DeviceRule.priority`
3. `DeviceRule`
   - binds one `DeviceConfig` to one target Device inside the root scope
   - compatibility rule:
     - `DeviceRule.deviceId` must point to a `Device` whose `deviceTypeEnumId`
       matches the `DeviceConfig.deviceTypeEnumId`

This means:

- `DeviceConfig` is type-level
- `DeviceRule` is instance-level
- `DeviceRuleSet` is the only multi-device composition mechanism
- each rule target must remain inside the root Device/DeviceGroup scope

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
- keep device ownership structural: use a leaf parameter alias such as
  `enableTime`, not `dev.coldGlycolPump.enableTime`
- stop and ask targeted follow-up questions if required data is missing

## Gotchas

- **`signal.device_id` must be an elementary device, never the root
  DeviceGroup.** `validate_upstream_surveys()` rejects a signal whose
  `device_id` is not one of the devices in
  `elementary-device-classification-survey.yaml`. But the device whose
  StatusFlow the FSM survey attaches to (and therefore the one that produces
  unprefixed `dev.<field>` names downstream, see
  `moqui-plc-designer`'s Gotchas) is always a `DeviceGroup`. In practice this
  means every signal you model ends up with a device-name-prefixed field on
  the PLC side (`dev.levelControllerLevelIn`, not `dev.levelIn`) — there is
  no combination of survey choices that gives you both a valid signal and an
  unprefixed field name. Pick device names accordingly; don't fight this by
  trying to attach a signal to the DeviceGroup id.
- **A supervisory/config value that isn't a physical signal and isn't an
  atomic-component field has no native way to become a ParameterDef.**
  `render_seed_from_surveys.py` only mints ParameterDef/Parameter rows from
  `append_atomic_component_parameters()` (one atomic component template) or
  from the `signals` loop (one per signal-catalog row). A free-standing value
  like an alarm threshold consumed only by `MainRuleEngine` fits neither.
  See `references/free-standing-parameters.md` for the accepted workaround
  before modeling one as a fake signal without reading it first — the
  workaround has real limits (wrong `purpose_enum_id`, no monitoring/control
  DeviceRequest by default) that are easy to get wrong silently.

## References

Start with the two workflow files; load everything else on demand, matched
to what's being modeled right now.

- `references/seed-survey-fields.md` — read at the start of any survey pass.
- `references/seed-output-workflow.md` — read before the first seed render
  of a session.
- `references/free-standing-parameters.md` — load only when a value doesn't
  fit a physical signal or an atomic-component field (a supervisory
  threshold, not sensor/actuator I/O).
- `references/atomic-component-library.json` — load when deciding which
  logical model (`Actuator`, `ProcessPid`, ...) fits a device, or which
  fields belong to its `configRecipe` group.
- `references/use-cases/mantle-hvac-reverse-engineering.md` and
  `references/mantle-hvac-like-seed-example.xml` — load only as a worked
  example when starting from an unfamiliar or ambiguous domain.
- `references/seed-bundle-spec.example.json` — load when composing a seed
  from fragments with `render_seed_bundle.py`.
- `references/<component>-seed-template.xml` (`base-device`,
  `digital-sensor`, `analog-sensor`, `actuator`, `actuator-group`,
  `process-pid`, `axis`, `axis-group`, `signal-mgmt`, `device-group`) — open
  only the one matching the device/signal type currently being modeled.
- `references/device-config-semantics.md` and
  `references/device-config-load-workflow.md` — read before authoring the
  first `DeviceConfig`/`DeviceRuleSet`/`DeviceRule` in a session.
- `references/device-config-template.xml` and
  `references/<component>-device-config-template.xml` (same component names
  as the seed templates above) — open only the one matching the atomic
  component whose recipe is being written.
- `references/mqtt-device-request-seed-template.xml`,
  `references/opcua-device-request-seed-template.xml`,
  `references/gateway-wrapper-request-seed-template.xml`,
  `references/framework-ec-seed-template.xml` — load the one matching the
  transport family actually being modeled for the current `DeviceRequest`.
- `references/framework-ec-requests.md` — load when modeling the standard
  framework `ec` read/write request family specifically.
- `references/mqtt-live-parameter-contract.md` — load before filling
  `live-parameters-survey.yaml` or reviewing a generated
  `JsonToParametersMapper`.

# Seed Output Workflow

Preferred workflow:

1. Collect upstream engineering data from user input or imported files:
   - system decomposition
   - elementary device classification
   - signal naming rules and normalized signal catalog
   - sampling domains
   - optional live-parameter whitelist
2. Normalize IDs, names, and enumerations.
3. Validate completeness against both:
   - Moqui entity models
   - the upstream engineering constraints captured in survey files
4. Emit a seed XML file in a staging/output location.
5. Let the user review the generated seed.
6. Only after approval, copy the seed into the chosen Moqui component path.

Important rule:

- the skill may prepare the destination path
- the final copy into a Moqui repository should happen only after user approval

Another important rule:

- if decomposition, device classification, signal semantics, or sampling-domain
  data are still partial, the workflow should ask targeted follow-up questions
  before emitting a seed that pretends to be complete

Bootstrap template:

- for the first practical seed template, prefer the patterns already used in
  `moqui-device-gateway/src/test/resources/device-gateway-seed.sql`
  and `device-gateway-opcua-seed.sql`
- convert those fixtures into reviewed Moqui XML seed files rather than inventing a structure from scratch

Recommended reference split:

- `base-device-seed-template.xml` for `Device`, `PhysicalDevice`, `ParameterDef`, `Parameter`
- `digital-sensor-seed-template.xml` for one digital sensor subtype such as `DtInputDigitalSensor` or `DtOutputDigitalSensor`
- `analog-sensor-seed-template.xml` for one analog sensor subtype such as `DtInputAnalogSensor` or `DtOutputAnalogSensor`
- `actuator-seed-template.xml` for on/off actuators
- `actuator-group-seed-template.xml` for staged actuator groups
- `process-pid-seed-template.xml` for process PID controllers
- `axis-seed-template.xml` for single servo axes
- `axis-group-seed-template.xml` for coordinated motion groups
- `signal-mgmt-seed-template.xml` for signal supervision blocks
- `device-group-seed-template.xml` for subsystem grouping through `DeviceGroup` and `DeviceGroupMember`
- `framework-ec-seed-template.xml` for standard `moqui-plc` framework-facing parameters and requests
- `mqtt-device-request-seed-template.xml` for the one standard live-parameter request
- `gateway-wrapper-request-seed-template.xml` for the standard recipe export wrapper
- `device-config-template.xml` for the first reusable TEMPLATE configuration and its first application rule
- `device-config-set-template.xml` for the first reusable TEMPLATE configuration set for a `DeviceGroup`
- `actuator-device-config-template.xml` for the configurable subset of an `Actuator`
- `actuator-group-device-config-template.xml` for the configurable subset of an `ActuatorGroup`
- `process-pid-device-config-template.xml` for the configurable subset of a `ProcessPid`
- `axis-device-config-template.xml` for the configurable subset of an `Axis`
- `axis-group-device-config-template.xml` for the configurable subset of an `AxisGroup`
- `signal-mgmt-device-config-template.xml` for the configurable subset of `SignalMgmt`

Standard request philosophy:

- treat the request layer as mostly standard
- do not proliferate many custom request families when a `moqui-plc` machine
  can usually be represented with:
  1. framework `ec` requests
  2. recipe export request
  3. one live MQTT parameter request for values acquired by `MqttParameterSub` in `moqui/moqui-plc` (with many `DeviceRequestItem` rows)

The old direct transport-oriented fragments may still be kept as internal
examples, but the normal workflow should start from the standard request
families above. In particular, `opcua-device-request-seed-template.xml` should
be treated as an auxiliary reference, not as the default workflow for
`moqui-plc` systems.

Reverse-engineering reference:

- `use-cases/mantle-hvac-reverse-engineering.md` shows how an existing PLC application can
  be decomposed into:
  - root machine device
  - atomic child devices
  - device groups
  - config/rule/recipe layers
- `mantle-hvac-like-seed-example.xml` provides one concrete stitched example of
  that decomposition in Moqui seed XML

DeviceConfig rule:

- once a device type already has its `ParameterDef` catalog, the skill can
  generate a first `DeviceConfig` marked `TEMPLATE`
- the user can later clone that template or fill in values through Moqui UI

Recipe-loading rule:

- `DeviceConfig` is always type-level, keyed by `deviceTypeEnumId`
- `DeviceConfigSet` is the analogous grouped template for a `DeviceGroup`
- `DeviceConfigSetMember` composes the grouped template
- `DeviceRule` is always instance-level, binding one `DeviceConfig` to one
  specific `Device`
- compatibility must be checked:
  - `Device.deviceTypeEnumId` must match `DeviceConfig.deviceTypeEnumId`
- `DeviceRuleSet` sequences the resulting application or validation rules

Composition helper:

- use `scripts/render_seed_bundle.py` to compose one final seed XML from the selected fragments
- use `references/seed-bundle-spec.example.json` as the starting spec format
- the bundle composer also supports:
  - `digital_sensor`
  - `analog_sensor`
  - `actuator`
  - `actuator_group`
  - `process_pid`
  - `axis`
  - `axis_group`
  - `signal_mgmt`
  - `device_group`
  - `device_config`
  - `device_config_set`
  - `actuator_config`
  - `actuator_group_config`
  - `process_pid_config`
  - `axis_config`
  - `axis_group_config`
- `signal_mgmt_config`

Question-guidance rule:

- treat the current data as the best source of the next question
- missing device-classification data should generate device-classification questions
- missing signal data should generate signal-catalog questions
- missing sampling data should generate timing-domain questions
- live-parameter questions should ask only which logical parameters are admitted
  to runtime change, not which FB parameters exist in theory
- only after these are materially complete should the workflow ask FSM and
  transition-condition questions

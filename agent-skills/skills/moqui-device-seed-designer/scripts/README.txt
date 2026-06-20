Helper scripts for moqui-device-seed-designer.

Current scripts:

- `render_atomic_component_template.py`
  - uses the canonical `references/atomic-component-library.json`
  - treats each `moqui-plc` atomic component as a model-driven library entry
  - can:
    - list available atomic components
    - describe one component and its semantic parameter groups
    - render a cloneable seed prototype directly from the library
    - optionally compose the reusable `DeviceConfig` / `DeviceRule` prototype too
  - auto-generates deterministic IDs for `PD_*`, `P_*`, and `CFG_P_*` placeholders so new devices do not need manual parameter inventories

- `render_seed_bundle.py`
  - composes a final Moqui seed XML from reusable template fragments
  - input is a JSON spec with:
    - `includes`
    - `variables`
  - validates that every `${PLACEHOLDER}` required by the selected templates is provided
  - if `--session-dir` is provided, writes by default into `seed-data/` and updates `session.json`
  - marks the session step as generated/review-needed rather than completed, so downstream PLC/gateway generation still treats the seed review as a required gate

- `render_seed_from_surveys.py`
  - renders a reviewable draft Moqui seed XML directly from the upstream engineering surveys
  - materializes:
    - root PLC/controller `Device` + `PhysicalDevice`
    - optional survey-derived gateway `Device` + `PhysicalDevice`
    - optional survey-derived `DeviceConnection` rows for `moqui-plc4j`
    - survey-derived elementary child `Device` + `PhysicalDevice` rows
    - subsystem and gateway `DeviceGroupMember` rows
    - signal-derived `ParameterDef` + `Parameter` rows
    - grouped physical I/O `DeviceRequest` + `DeviceRequestItem` rows for:
      - `moqui-device-gateway` using signal names / MQTT semantics
      - `moqui-plc4j` using explicit `plc4j_query` values from the surveys
  - runs the upstream survey validation first, so partial surveys block generation
  - keeps the output explicitly reviewable rather than pretending that all enums or grouping decisions are final

- `validate_transport_projection.py`
  - validates that the resulting seed projects onto at least one real transport layer
  - accepted transport projections today:
    - `moqui-device-gateway` via `routerEnumId = DrrMoquiDeviceGateway`
    - `moqui-plc4j` via `runServiceName = moqui.plc4j.Plc4jServices.run#Plc4jRequest`
  - checks coherence of `DeviceConnection`, `connectionName`, `routerEnumId`, and gateway scope markers

Known includes:

- `base`
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
- `mqtt`
- `gateway_wrapper`
- `framework_ec`
- `opcua` (auxiliary direct-transport reference; not part of the normal minimal moqui-plc request set)

Example:

```bash
python3 scripts/render_seed_bundle.py \
  references/seed-bundle-spec.example.json \
  --output /tmp/virtual-plc-seed.xml

python3 scripts/render_seed_bundle.py \
  references/seed-bundle-spec.example.json \
  --session-dir ../../output/sessions/demo-plant-session \
  --output-name reviewed-device-seed.xml

python3 scripts/render_seed_from_surveys.py \
  --session-dir ../../output/sessions/demo-plant-session \
  --output-name survey-derived-seed.xml

python3 scripts/render_atomic_component_template.py \
  actuator \
  --include-config \
  --output /tmp/actuator-template.xml

python3 scripts/validate_transport_projection.py \
  --session-dir ../../output/sessions/demo-plant-session
```

Ready-made examples:

- `references/seed-bundle-spec.mqtt-framework.example.json`
- `references/seed-bundle-spec.opcua-gateway-wrapper.example.json`
- `references/seed-bundle-spec.actuator-group.example.json`
- `references/seed-bundle-spec.digital-sensor.example.json`
- `references/seed-bundle-spec.analog-sensor.example.json`
- `references/seed-bundle-spec.actuator-config.example.json`
- `references/seed-bundle-spec.process-pid-config.example.json`
- `references/seed-bundle-spec.axis-group-config.example.json`

Helper scripts for moqui-plc-designer.

Current scripts:

- `render_statusflow_templates.py`
  - reads a Moqui seed XML containing `StatusFlow` data
  - extracts `StatusFlowItem` and `StatusFlowTransition`
  - renders a component-like output tree under `output/<component-name>/`
  - writes:
    - `src/main/<namespace>/<component-name>/MainStatus.dut`
    - `src/main/<namespace>/<component-name>/Main.pou`
    - `src/main/<namespace>/<component-name>/MainRuleEngine.pou`
    - `src/main/org/moqui/device/IOFacade.dut`
    - `src/main/org/moqui/device/DeviceFacade.dut`
  - `src/main/org/moqui/device/DeviceManager.pou`
  - `src/main/org/moqui/device/DeviceDiagnostics.pou`
  - fills structural placeholders only
  - leaves process predicates and transition semantics as TODO placeholders
  - uses the default convention `StatusName -> statusNameRequest`
  - accepts an optional JSON request map only for exceptional overrides
  - supports optional explicit `--fault-state` and `--break-state`
  - if `--session-dir` is provided, writes by default into `generated-plc/` and updates `session.json`
  - validates the selected `StatusFlow` before rendering:
    - exactly one initial state
    - no missing `StatusItem` rows
    - no transition targets outside the selected flow
    - no enum-name normalization collisions

Example:

```bash
python3 scripts/render_statusflow_templates.py \
  /path/to/DeviceData.xml \
  DeviceBasicStatusFlow \
  ./output \
  --component-name hvac \
  --namespace mantle

python3 scripts/render_statusflow_templates.py \
  /path/to/DeviceData.xml \
  DeviceBasicStatusFlow \
  --session-dir ../../output/sessions/demo-plant-session \
  --component-name hvac \
  --namespace mantle
```

Example request map:

```json
{
  "Run": "runRequest",
  "ErrorStop": "faultRequest"
}
```

Use it like this:

```bash
python3 scripts/render_statusflow_templates.py \
  /path/to/DeviceData.xml \
  DeviceBasicStatusFlow \
  ./output \
  --component-name motion \
  --request-map ./request-map.json
```

- `render_device_catalog_from_seed.py`
  - reads one or more Moqui seed XML files
  - joins:
    - `Device`
    - `PhysicalDevice`
    - `ParameterDef`
    - `Parameter`
    - `DeviceRequest`
    - `DeviceRequestItem`
  - renders:
    - `src/main/org/moqui/device/DeviceFacade.dut`
    - `src/main/org/moqui/device/IOFacade.dut`
    - `src/main/org/moqui/device/DeviceManager.pou`
    - `src/main/org/moqui/device/DeviceDiagnostics.pou`
  - derives logical parameter declarations from `ParameterDef` and `Parameter`
  - includes parameters of the root device and its child devices
  - derives physical signal declarations from `DeviceRequestItem`
  - derives part of the atomic device catalog from child `Device` rows using `deviceTypeEnumId`, `controlMethodEnumId`, and `PhysicalDevice.deviceName`
  - now emits deterministic `DeviceFacade` / `DeviceManager` generation for:
    - `Actuator`
    - `ActuatorGroup`
    - `ProcessPid`
    - `Axis`
    - `AxisGroup`
    - `SignalMgmt`
  - target convention:
    - emit full-signature FB calls every scan
    - avoid partial calls that omit unchanged parameters
  - for `Axis` and `AxisGroup`, some generated fields intentionally correspond to CODESYS device-tree objects rather than Moqui seed data
  - placeholders are acceptable there and are expected to be corrected or bound by the user in the CODESYS project
  - generates a first deterministic blocking-device `DeviceDiagnostics` scaffold using child FB output signals
  - leaves predicates, safety/environment rules, and fieldbus mapping as TODO/manual
  - if `--session-dir` is provided, writes by default into `generated-plc/` and updates `session.json`
  - validates the seed graph before rendering:
    - root device exists
    - root `PhysicalDevice` exists
    - `Parameter` -> `ParameterDef` / `Device` references resolve
    - `DeviceRequest` / `DeviceRequestItem` references resolve
    - generated IEC field names do not collide silently

- `validate_generated_plc_against_seed.py`
  - compares generated PLC declarations back to the seed-derived catalog
  - checks that:
    - `DeviceFacade` still exposes all logical parameters and state request flags derived from seed data
    - `IOFacade` still exposes all physical I/O declarations derived from `DeviceRequestItem`
    - `MainStatus.dut` still contains every state declared in the selected `StatusFlow`
  - use this after generation or after manual edits to keep the model data as the source of truth

Current boundary:

- treat `DeviceFacade`, `DeviceManager`, and `DeviceDiagnostics` as the stable
  generated catalog/orchestration layer for supported atomic moqui-plc FB types
- treat `Main` and `MainRuleEngine` as intentionally unfinished behavior-layer
  artifacts pending extraction of final rules from real test cases
- treat the repository as a semilavorato/base framework that project teams may
  specialize further

Example:

```bash
python3 scripts/render_device_catalog_from_seed.py \
  /path/to/PlantSeedData.xml \
  /path/to/DeviceData.xml \
  --device-id VIRTUAL_PLC \
  --component-name virtual-plc \
  --namespace mantle \
  --output-root ./output \
  --request-map ./request-map.json

python3 scripts/render_device_catalog_from_seed.py \
  /path/to/PlantSeedData.xml \
  --device-id VIRTUAL_PLC \
  --component-name virtual-plc \
  --namespace mantle \
  --session-dir ../../output/sessions/demo-plant-session

python3 scripts/validate_generated_plc_against_seed.py \
  /path/to/PlantSeedData.xml \
  --device-id VIRTUAL_PLC \
  --component-root ../../output/sessions/demo-plant-session/generated-plc/virtual-plc
```

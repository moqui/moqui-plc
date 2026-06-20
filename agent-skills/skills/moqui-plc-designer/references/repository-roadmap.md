# Repository Roadmap

## Current focus

Build the first usable skills:

- `moqui-plc-designer`
- `moqui-device-seed-designer`

These skills should guide:

- Moqui seed-data design and validation
- `StatusFlow` definition or specialization
- PLC skeleton generation for V1
- seed-first generation from versionable Moqui XML data
- seed XML emission for Moqui data authoring

## V1 boundaries

In scope:

- `IOFacade`
- `DeviceFacade`
- `DeviceManager`
- `DeviceDiagnostics`
- `Main`
- `MainRuleEngine`
- simple blocking-device diagnostics
- simple machine/subsystem decomposition

Out of scope:

- `InputSignalUpdate`
- `OutputSignalUpdate`
- physical field wiring automation
- automatic interpretation of electrical schematics
- redundancy / backup / standby groups
- non-blocking `DeviceGroupMember` roles
- fully automatic rule-engine synthesis without user confirmation

## Likely next skills

### `moqui-device-config-designer`

Focus:

- generate PLC config/txtrecipe templates from `DeviceFacade`
- include top-level configurable parameters plus FB configuration fields
- support tests and installations that use a PLC-side HMI without Moqui as the primary UI

### `plc-facade-generator`

Focus:

- deterministic rendering of `IOFacade` and `DeviceFacade`

### `plc-fsm-generator`

Focus:

- deterministic rendering of `Main` and `MainRuleEngine`

### `plc-plant-cloner`

Focus:

- clone a plant from template data and spreadsheet-like specifications

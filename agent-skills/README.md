# Agent Skills

Repository for skill-driven PLC and Moqui code generation assets.

Python helper scripts depend on:

- `PyYAML` for survey parsing and validation

Install with:

```bash
python3 -m pip install -r requirements.txt
```

Regression tests:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

Transport projection rule:

- every generated/reviewed seed must project onto at least one real transport layer
- accepted transport projections today are:
  - `moqui-device-gateway`
  - `moqui-plc4j`

This repository is meant to host:

- `SKILL.md` files for repetitive PLC/Moqui engineering workflows
- reusable code generation templates
- helper scripts for deterministic generation steps
- reference material derived from `moqui-device`, `moqui-math`, and `moqui-plc`

Current design direction:

- seed-first generation using Moqui XML seed data as the single source of truth
- upstream system-engineering decomposition and device/signal classification as
  prerequisites for complete seed authoring
- PLC artifact generation from seed data plus PLC-side templates
- physical wiring and protocol-specific signal mapping kept manual

Current top-level skills:

- `skills/moqui-plant-designer`
- `skills/moqui-plc-designer`
- `skills/moqui-device-seed-designer`
- `skills/moqui-plc-config`
- `skills/moqui-device-gateway-startup`

Internal/support skill:

- `skills/moqui-device-config-designer`

Current scope:

- capture upstream engineering constraints before seed generation:
  - system decomposition
  - elementary device classification
  - signal naming/catalog
  - sampling domains
- generate or guide seed data design for devices, parameters, requests, and status flows
- persist a resumable session workspace that can be zipped, copied, and committed
- generate PLC code skeletons for:
  - `IOFacade`
  - `DeviceFacade`
  - `DeviceManager`
  - `DeviceDiagnostics`
  - `Main`
  - `MainRuleEngine`
- treat `DeviceFacade`, `DeviceManager`, and `DeviceDiagnostics` as the stable
  generated layer for supported atomic moqui-plc FB types
- keep `Main` and `MainRuleEngine` in standby until real project test cases are
  available to derive the final behavioral generation rules
- keep `InputSignalUpdate` and `OutputSignalUpdate` manual in V1
- keep complex `DeviceGroup` redundancy / standby roles out of scope in V1
- prefer Moqui seed data in XML format for data creation/update workflows
- keep Moqui seed/model data as the source of truth and treat generated PLC
  artifacts as reviewable runtime projections that must be cross-checked back
  against seed data before use

Relevant references currently moved here:

- `skills/moqui-plc-designer/references/plc-codegen-templates.md`
- `skills/moqui-plc-designer/references/plc-codegen-templates/`

The structure intentionally follows a lightweight skill-repository model similar to
`schue/moqui-skill`, rather than a deployable Moqui runtime component.

At this stage the repository should be considered a semilavorato/base framework
to be specialized by each development team rather than a finished turnkey
component.

Current repository layout:

- `skills/`
  - one directory per skill
- `skills/<skill>/references/`
  - docs, schemas, examples, templates
- `skills/<skill>/scripts/`
  - helper generators or validators

Planned evolution:

- refine `moqui-plant-designer` as the parent workflow orchestrator
- refine `moqui-plc-designer` around seed-first PLC code generation
- refine `moqui-device-seed-designer` around survey-style seed authoring and validation
- refine `moqui-plc-config` around guided `MoquiConf.gvl` compilation
- keep `moqui-device-config-designer` as an internal helper for recipe/config template workflows and non-Moqui HMIs such as CODESYS HMI
- add a guided first-startup workflow for `moqui-device-gateway`, driven from reviewed seed data and gateway runtime discovery rules
- add an eval workspace for skill quality regression using saved sessions as realistic fixtures
- strengthen automated model-vs-generated cross-checks so the seed/model stays
  the persistent declaration layer for both PLC and gateway outputs

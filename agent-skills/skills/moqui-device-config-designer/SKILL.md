---
name: moqui-device-config-designer
description: Use when generating or validating PLC config or txtrecipe templates such as `*.HvacDeviceConfig.txtrecipe` or `*.DeviceConfig.txtrecipe`. This internal skill derives config structure from DeviceFacade declarations, provides example templates, and supports tests or installations that use a PLC or CODESYS HMI without Moqui as the primary machine UI.
compatibility: Requires Python 3.14+
license: ../../LICENSE.md
metadata:
  author: moqui-industrial
  version: "1.0"
---

# Moqui Device Config Designer

Use this skill when the task is to create or validate config or recipe template files such as:

- `*.HvacDeviceConfig.txtrecipe`
- `*.DeviceConfig.txtrecipe`

## Goal

Generate a config or recipe template that contains the full recipe surface exposed by `DeviceFacade`, including:

- every top-level logical variable in `DeviceFacade` that is meant to be assigned by recipe
- every field of the instantiated atomic FBs that belongs to the fixed allowed list for that FB type:
  - `Actuator`
  - `ActuatorGroup`
  - `Axis`
  - `AxisGroup`
  - `SignalMgmt`
  - `ProcessPid`

For this repository, a recipe can be treated simply as:

```text
dev.path:=value
```

That is enough to express the PLC-side configuration surface.

The leading `dev.` is added only to the generated CODESYS recipe. Never store
that prefix in Moqui `PhysicalDevice.deviceName`, `ParameterDef.parameterName`,
or `Parameter.parameterAlias`.

Canonical PLC source repository:

- [moqui/moqui-plc](https://github.com/moqui/moqui-plc)

## Core Rule

A recipe template should contain:

1. every eligible top-level variable in `DeviceFacade`
2. every eligible field of each FB instance declared in `DeviceFacade`

Feedback values should not be included in recipes.

If the Moqui data model distinguishes them with `purposeEnumId`, use a dedicated purpose such as `PpFeedback` to exclude them systematically.

## References

- `references/recipe-generation-rules.md`
- `references/recipe-example-phase1-hvac-cooling.txt`
- `references/recipe-template.HvacDeviceConfig.txtrecipe`

## Preferred Derivation Strategy

Prefer this order of derivation:

1. derive the recipe structure directly from `DeviceFacade` in `moqui/moqui-plc`
2. use seed XML when device metadata or naming conventions are needed
3. create or update Moqui data using seed XML, not ad-hoc direct DB writes

This keeps config generation aligned with the real PLC model rather than with incomplete or stale DB data.

## Position In The Repository

This is an internal/support skill.

Typical uses:

- offline template generation for tests
- example config files for documentation
- installations where a CODESYS HMI or another PLC-side HMI is used without Moqui as the primary UI
- consistency checks between `DeviceFacade` and exported config files

## Questions To Ask

- Which `DeviceFacade` file is the source of truth?
- Should the output be a reusable template recipe with example values?
- Should the output be sorted by:
  - top-level simple parameters first
  - then grouped by FB instance
  - then alphabetically by field

## Output Style

- Emit one assignment per line in `dev.path:=value` format
- In a saved parent session, prefer `output/sessions/<session-id>/generated-recipes/`
- Preserve stable ordering
- Prefer reusable recipe templates with example values
- Prefer deriving recipe lines from `DeviceFacade` over deriving them from `Parameter` rows alone
- Exclude feedback values from recipes
- Prefer Moqui seed XML when new `ParameterDef` / `Parameter` data must be created
- Prefer session-aware helpers so `session.json` is updated together with the generated recipe artifact

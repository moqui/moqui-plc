---
name: moqui-plc-config
description: Use when configuring moqui-plc framework constants in MoquiConf.gvl. This skill runs a guided section-by-section workflow, asks only the relevant configuration questions, skips protocol sections that do not apply, and prepares reviewable values for the constants declared in MoquiConf.gvl.
compatibility: Requires Python 3.14+
license: ../../LICENSE.md
metadata:
  author: moqui-industrial
  version: "1.0"
---

# Moqui PLC Config

Use this skill when the task is to collect, validate, and prepare configuration values for:

- [moqui/moqui-plc](https://github.com/moqui/moqui-plc)
- `iec61131/moqui/framework/src/main/resources/MoquiConf.gvl`

## Goal

Guide the user through the configuration of `MoquiConf.gvl` section by section and produce a reviewable set of constant values for the chosen deployment.

## Workflow

1. Read `MoquiConf.gvl`.
2. Ask the configuration questions in section order.
3. Skip sections that do not apply to the chosen architecture.
4. Produce a reviewable configuration summary or filled template.
5. After user approval, prepare the edited `MoquiConf.gvl` values or a patch plan.

## Section Order

Ask the sections in this order:

1. `Framework`
2. `Logger`
3. `Communication Protocols`
4. protocol-specific subsection:
   - `Modbus` if the fieldbus is Modbus-based
   - `MQTT` only if MQTT is used
   - omit MQTT questions if the user chooses OPC UA exposure instead of MQTT
5. `Signal Management`
6. `Device Config Management`

## Conditional Logic

- If the user exposes PLC data via OPC UA instead of MQTT, skip the MQTT section.
- If the user uses MQTT, ask all connection, topic, QoS, retain, and publish/subscribe questions.
- If the user does not use Modbus, do not insist on Modbus overrange/overflow tuning.
- Keep the workflow architecture-driven rather than asking every constant blindly.

## Output Style

- preserve original constant names from `MoquiConf.gvl`
- in a saved parent session, prefer `output/sessions/<session-id>/generated-config/`
- group answers by section
- keep defaults visible when the user accepts them
- clearly distinguish:
  - accepted defaults
  - user-overridden values
  - omitted sections
- prefer session-aware helpers so `session.json` is updated together with the generated checklist

## References

- `references/moqui-conf-sections.md`
- `references/moqui-conf-question-flow.md`
- `references/moqui-conf-template.md`

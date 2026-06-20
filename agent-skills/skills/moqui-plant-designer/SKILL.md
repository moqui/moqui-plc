---
name: moqui-plant-designer
description: Use when orchestrating the full AI-assisted workflow for a machine or plant: create and resume a saved project session, drive Moqui seed-data authoring, generate PLC code from seed XML, and derive PLC config or recipe templates from the same seed source of truth.
compatibility: Requires Python 3.14+
license: ../../LICENSE.md
metadata:
  author: moqui-induatrial
  version: "1.0"
---

# Moqui Plant Designer

Use this skill as the parent orchestrator for the full workflow.

This skill does not replace the specialist skills. It coordinates them, keeps
session state on disk, and knows where the workflow should resume after an
interruption.

## Source Of Truth

The single source of truth is the Moqui seed XML generated during the session.

Do not treat direct database reads as part of the primary workflow. If existing
data must be imported, convert it into seed XML and keep working from the saved
session files.

## What This Skill Orchestrates

Main ordered flow:

1. system decomposition
2. elementary device classification
3. signal catalog and naming rules
4. sampling-domain design
5. transport-architecture design
6. `moqui-device-seed-designer`
7. `moqui-plc-designer`
8. `moqui-device-config-designer`

Optional branch:

4. `moqui-plc-config`
5. `moqui-device-gateway-startup`

Use `moqui-plc-config` only when the deployment also needs guided compilation
of `MoquiConf.gvl`.

Use `moqui-device-gateway-startup` when the reviewed seed should also drive a
guided first startup of `moqui-device-gateway`.

## Session Workspace

Every run should live in a saved session directory.

Default location:

- `output/sessions/<session-id>/`

Minimum structure:

- `session.json`
- `survey-answers/`
- `seed-data/`
- `generated-plc/`
- `generated-recipes/`
- `generated-config/`
- `attachments/`
- `notes/`
- `exports/`

The workspace should be:

- resumable
- zip-exportable
- git-friendly
- copyable between computers

## Workflow

1. Initialize or open a session workspace.
2. Record high-level project metadata in `session.json`.
3. Collect and persist the system decomposition down to elementary devices.
4. Classify each elementary device by logical model and actuation/feedback pattern.
5. Derive and persist physical signal naming rules plus the normalized signal catalog.
6. Group devices/signals by natural frequency and sampling domain.
7. Record whether the plant projects onto `moqui-device-gateway`, `moqui-plc4j`, or both.
8. Run `moqui-device-seed-designer` and keep the reviewed seed XML in `seed-data/`.
   Prefer session-aware helpers such as `render_seed_bundle.py --session-dir ...`.
9. Run `moqui-plc-designer` only against the seed XML saved in the workspace.
10. Run `moqui-device-config-designer` only against the same seed XML and generated PLC artifacts.
11. Optionally run `moqui-plc-config` for `MoquiConf.gvl`.
12. Optionally run `moqui-device-gateway-startup` to generate a first-startup checklist from the reviewed seed.
13. Update `session.json` after each step so the workflow can resume cleanly.
14. Export the session as a zip when the user wants backup, transfer, or archival.

## Required Behavior

- prefer deterministic files over hidden ephemeral context
- keep every generated artifact inside the session workspace
- do not scatter final artifacts into `/tmp`
- when the workflow is resumed, inspect `session.json` first
- if reviewed seed XML already exists, treat it as canonical input for downstream skills
- store user answers and imported attachments inside the workspace
- use upstream survey answers as the first source of constraints and guided questions
- do not ask FSM questions before system decomposition, device classification,
  signal semantics, and sampling-domain design are materially captured

## Helper Scripts

- `scripts/init_session.py`
  - creates a new session workspace and bootstraps `session.json`
- `scripts/render_guided_questions.py`
  - inspects the saved surveys plus the atomic-component library
  - writes the next model-driven guided questions into `notes/guided-questions.md`
  - asks only for missing contextual data, not for logical parameters already fixed by the chosen atomic component
- `scripts/export_session_bundle.py`
  - zips a saved session and writes a manifest with checksums

## References

- `references/session-layout.md`
- `references/session-schema.json`
- `references/workflow-order.md`
- `scripts/README.txt`

## Output Style

- keep the session structure stable
- update status fields instead of inventing ad-hoc notes
- write concise machine-readable state into `session.json`
- keep human notes in `notes/`

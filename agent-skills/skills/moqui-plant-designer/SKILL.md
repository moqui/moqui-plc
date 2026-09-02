---
name: moqui-plant-designer
description: "Use when orchestrating the full AI-assisted workflow for a machine or plant: create and resume a saved project session, drive Moqui seed-data authoring, generate PLC code from seed XML, and derive PLC config or recipe templates from the same source model."
---

# Moqui Plant Designer

Use this skill as the parent orchestrator for the full workflow.

This skill does not replace the specialist skills. It coordinates them, keeps
session state on disk, and knows where the workflow should resume after an
interruption.

Before any project action, read `references/project-architecture.md` completely.
When operating in the `moqui-plc` checkout, follow the repository `AGENTS.md`
bootstrap and resolve `agent-skills/CURRENT_SESSION` before asking the user to
repeat project context. When resuming a saved session, also read its
`session.json`, `notes/project-architecture-context.md` and
`notes/resume-summary.md`. Load `notes/conversation-history.md` only when the
reason for a historical decision is relevant.

## Source Of Truth

Moqui seed XML is authoritative for the device tree, parameters, transport
requests, StatusFlow states, and transition topology. PLC source is authoritative
for predicates, state output functions, interlocks, and deterministic call order.

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
6. `moqui-hvac-demo-guide` for the repository's supported local HVAC demo only

Use `moqui-plc-config` only when the deployment also needs guided compilation
of `MoquiConf.gvl`.

Use `moqui-device-gateway-startup` when the reviewed seed should also drive a
guided first startup of `moqui-device-gateway`.

Use `moqui-hvac-demo-guide` only to execute and verify the supported local HVAC
demonstration. Do not generalize it into a production deployment or use it as a
commissioning workflow for another plant model.

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

Commit the state, surveys, reviewed seed and durable notes when the user wants a
portable handoff. Do not commit ZIP exports, secrets, database contents, runtime
logs or source snapshots that merely duplicate tracked repository files.

## Workflow

1. Initialize or open a session workspace.
2. Record high-level project metadata in `session.json`.
3. Collect and persist the system decomposition down to elementary devices.
4. Classify each elementary device by logical model and actuation/feedback pattern.
5. Derive and persist physical signal naming rules plus the normalized signal catalog.
6. Group devices/signals by natural frequency and sampling domain.
7. Define every hardware CPU or CODESYS Application as a distinct `PhysicalDevice`.
8. Have the developer define DeviceGroups and membership explicitly; never infer redundancy or operational roles.
9. Define one FSM for each system/subsystem that needs an independently visible state. Prefer flat FSMs; use nested flows only when a real push-down behavior is required.
10. Record whether the plant projects onto `moqui-device-gateway`, `moqui-plc4j`, or both.
11. Run `moqui-device-seed-designer` and keep the reviewed seed XML in `seed-data/`.
   Prefer session-aware helpers such as `render_seed_bundle.py --session-dir ...`.
   This step is not complete once the atomic-component defaults are in the
   seed: any atomic-component parameter whose real value differs from its
   template default (a real PID gain, a real setpoint, a real threshold) only
   reaches the generated PLC through a `DeviceConfig` applied by a
   `DeviceRuleSet`/`DeviceRule` in this same seed. Skipping that leaves the
   generated code compiling and running against the template's literal
   defaults with no warning at any later step.
12. Run `moqui-plc-designer` only against the seed XML saved in the workspace.
13. Run `moqui-device-config-designer` only against the same seed XML and generated PLC artifacts.
14. Optionally run `moqui-plc-config` for `MoquiConf.gvl`.
15. Optionally run `moqui-device-gateway-startup` to generate a first-startup checklist from the reviewed seed.
16. For the repository HVAC demo only, optionally run `moqui-hvac-demo-guide` to prove both MQTT directions.
17. Update `session.json` after each step so the workflow can resume cleanly.
18. Export the session as a zip when the user wants backup, transfer, or archival.

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
- `scripts/render_engineering_dossier.py`
  - consolidates approved surveys into Markdown
  - optionally emits a complete approved HiveMind WorkEffort project with milestones, tasks and linked WikiPage
- `scripts/analyze_eplan_sources.py`
  - parses EPLAN UTF-16 semicolon CSV exports with two header rows
  - records PDF/CSV provenance and emits review candidates without deciding physical binding or safety semantics

## References

- `references/project-architecture.md` (mandatory at session start/resume)
- `references/moqui-math-knowledge.md` (load for mathematical models/parameters)
- `references/moqui-device-knowledge.md` (load for device seed/entities/services)
- `references/moqui-device-gateway-knowledge.md` (load for transport/runtime work)
- `references/moqui-plc-knowledge.md` (load for deterministic PLC/code generation)
- `references/session-layout.md` (load when creating or restructuring a session workspace by hand)
- `references/session-schema.json` (load when validating or hand-editing `session.json`)
- `references/workflow-order.md` (load when unsure which stage comes next for the current session)
- `references/controller-and-group-model.md` (load before defining `PhysicalDevice`/`DeviceGroup` topology)
- `references/eplan-source-workflow.md` (load only when importing EPLAN CSV/PDF sources)
- `scripts/README.txt` (load before running any helper script for the first time in a session)

## Output Style

- keep the session structure stable
- update status fields instead of inventing ad-hoc notes
- write concise machine-readable state into `session.json`
- keep human notes in `notes/`

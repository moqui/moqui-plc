---
name: moqui-hvac-demo-guide
description: Guide and verify the local Moqui HVAC end-to-end demonstration across PostgreSQL, moqui-device seed data, ActiveMQ Artemis MQTT v5, moqui-device-gateway, Mosquitto clients, and a CODESYS Control Win runtime. Use when an inexperienced developer wants to prepare, start, resume, troubleshoot, verify, or stop the supported HVAC demo; do not use it for production deployment, Kubernetes, Swarm, high availability, or industrial commissioning.
---

# Moqui HVAC Demo Guide

Guide the user through the supported local HVAC demonstration one observable
checkpoint at a time. Treat the `End-to-End HVAC demo` section in the root
`moqui-plc/README.md` as the canonical command reference.

## Scope

Operate only a local developer demonstration composed of:

- Moqui-managed PostgreSQL data loaded from `moqui-device/data/HVACDemoData.xml`
- ActiveMQ Artemis as the MQTT v5 broker
- `moqui-device-gateway` running locally
- Mosquitto command-line clients as observers or test publishers
- `codesys/moqui.projectarchive` running on CODESYS Control Win

Do not present this workflow as a production deployment. Do not design or
configure Kubernetes, Swarm, TLS, secret management, backups, network
segmentation, redundancy, safety, physical I/O, or FAT/SAT commissioning.

## Required Sources

Before issuing commands:

1. Locate the workspace containing sibling `moqui-*` repositories.
2. Read the complete `End-to-End HVAC demo` section in `moqui-plc/README.md`.
3. Read `references/demo-workflow.md` for checkpoint and interaction rules.
4. Read `references/troubleshooting.md` only when a checkpoint fails.
5. Consult `moqui-device-gateway/README.md` when gateway commands or behavior
   differ from the root demo documentation.

Prefer repository files over remembered commands. Report any disagreement
between documentation and the current source before continuing.

## Workflow

1. Run the non-mutating preflight checker:

   ```text
   python moqui-plc/agent-skills/skills/moqui-hvac-demo-guide/scripts/check_demo_prerequisites.py --workspace <workspace>
   ```

2. Explain the two data directions and the identities involved before starting
   infrastructure.
3. Establish the user's current checkpoint. Resume healthy existing services
   instead of restarting them unnecessarily.
4. Guide the phases in order:
   - PostgreSQL and reviewed HVAC seed
   - Artemis MQTT broker
   - Mosquitto observer
   - `moqui-device-gateway` and health
   - CODESYS Control Win, task calls, login, and Run
   - direct MQTT live-parameter update
   - modeled gateway-to-PLC request
   - PLC-to-gateway parameter/device log persistence
5. At each phase, state:
   - the exact action
   - the expected evidence
   - the next diagnostic if evidence is absent
6. Record the final result as passed, partially passed, or blocked, including
   the last proven checkpoint and relevant command output.
7. Offer the documented non-destructive shutdown commands. Never add volume
   deletion flags unless the user explicitly requests data removal.

## Interaction Rules

- Perform safe command-line checks and local demo actions when authorized.
- Ask the user to perform CODESYS GUI operations and wait for their result.
- Never infer that IDE Simulation proves MQTT connectivity; use CODESYS Control
  Win for the complete transport test.
- Never put development credentials into official seed files or commits.
- Never change physical bindings, device trees, safety logic, or production
  configuration as part of this demo.
- Do not claim success from process startup alone. Require evidence in both
  MQTT directions and, for the return path, database persistence.
- Use exact modeled identifiers. In particular, distinguish
  `Device.deviceId` from `Parameter.parameterId` in log events.

## Completion Criteria

Declare the complete demo passed only when all of these are observed:

- gateway health is `UP`
- CODESYS `MqttParameterSub` is connected
- a whitelisted MQTT update changes the expected `DeviceFacade` parameter
- the modeled gateway request publishes its HVAC parameter set
- CODESYS `LogDispatcher` publishes a `ParameterLogger` event
- the gateway persists that event using its exact parameter identity

Partial transport tests may be reported separately, but never as full
end-to-end success.

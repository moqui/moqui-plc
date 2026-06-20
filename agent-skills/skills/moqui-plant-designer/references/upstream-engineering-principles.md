# Upstream Engineering Principles

The workflow must treat engineering data as the primary source of constraints.

The agent should not begin with PLC code questions. It should begin with the
structure of the controlled system and derive later questions from that model.

## Canonical order

1. decompose the machine/plant into subsystems
2. decompose each subsystem until elementary devices are identified
3. classify each elementary device by logical model and actuation/feedback class
4. derive the expected physical I/O signals from the classification
5. define signal naming and logic conventions
6. group signals/devices by natural frequency and sampling domain
7. author seed data
8. derive PLC FSMs and generated artifacts from the reviewed seed

## Device actuation/feedback classes

Use explicit classes such as:

- `DA-DF`
- `SA-DF`
- `SA-SAFD`
- `SA-SDFD`
- `SA-NO`

These classes are not just labels. They are constraints that should drive:

- which physical signals must exist
- which questions the agent asks
- what the expected logical device interface looks like

## Data-driven questioning rule

At every stage, the next questions should come from missing or ambiguous data in
the current model, not from a generic questionnaire detached from context.

Examples:

- missing device classification -> ask device-classification questions
- classified device but missing expected signals -> ask signal questions
- signal catalog present but missing timing groups -> ask sampling questions
- only after these are present -> ask FSM and transition questions

## PLC and gateway consequence

Generated PLC code and gateway runtime behavior are projections of the model.

Therefore:

- do not let generated code become the hidden source of truth
- keep the persistent declaration layer in seed/model data
- prefer validation and cross-checks that compare generated artifacts back to the
  model data

# Workflow Order

## Primary path

1. system decomposition
2. elementary device classification
3. signal catalog and naming-rule design
4. sampling-domain design
5. `moqui-device-seed-designer`
6. `moqui-plc-designer`
7. `moqui-device-config-designer`

## Optional path

8. `moqui-plc-config`
9. `moqui-device-gateway-startup`

## Rationale

The seed XML is the digital twin and the canonical design model, but it should
only be authored after the upstream engineering constraints are captured.

Everything else should depend on that:

- PLC code
- recipes
- framework configuration notes
- gateway startup guidance
- transport projection validation (`gateway` and/or `plc4j`)

This avoids drift between:

- system-engineering decomposition
- Moqui-side data
- PLC-side declarations
- commissioning artifacts

It also ensures that:

- device classification determines which physical signals must exist
- signal semantics and naming rules are derived before PLC declarations
- sampling domains are captured before transport/polling decisions
- FSM questions are guided by device and signal data rather than by guesswork

## Evaluation note

It makes sense to evaluate these skills with saved sessions as realistic fixtures.

A practical eval loop can compare:

- with skill vs without skill
- current skill vs previous revision

and grade:

- completeness of seed XML
- presence of expected PLC artifacts
- recipe/config outputs
- session-state correctness in `session.json`

Repository regression tests should keep at least one saved-fixture-like gateway
session path under automated coverage so survey validation, seed generation, and
gateway startup guidance are exercised together.

## Resume Rule

When resuming a project:

1. open `session.json`
2. inspect which upstream engineering surveys are still incomplete
3. check whether reviewed seed XML already exists
4. continue from the first incomplete stage

Do not skip directly to PLC generation when decomposition, device
classification, signal semantics, or sampling-domain design are still partial.

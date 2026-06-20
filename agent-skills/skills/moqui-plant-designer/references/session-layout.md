# Session Layout

Recommended persistent workspace layout:

```text
output/sessions/<session-id>/
├── session.json
├── survey-answers/
├── seed-data/
├── generated-plc/
├── generated-recipes/
├── generated-config/
├── attachments/
├── notes/
└── exports/
```

## Purpose Of Each Directory

- `survey-answers/`
  - normalized answers collected during the workflow
  - standard files:
    - `main-fsm-survey.yaml`
    - `main-rule-engine-survey.yaml`
- `seed-data/`
  - reviewed Moqui seed XML
- `generated-plc/`
  - PLC code emitted by `moqui-plc-designer`
- `generated-recipes/`
  - recipe or txtrecipe outputs
- `generated-config/`
  - `MoquiConf.gvl` checklists, patches, or generated config summaries
- `attachments/`
  - imported PDFs, spreadsheets, copied specs, diagrams
- `notes/`
  - human-readable notes, decisions, open questions
- `exports/`
  - zip bundles and export manifests

## Standard PLC Survey Files

- `survey-answers/system-decomposition-survey.yaml`
  - hierarchical decomposition of the machine/plant into subsystems down to elementary devices
- `survey-answers/elementary-device-classification-survey.yaml`
  - logical model + actuation/feedback class of each elementary device
- `survey-answers/signal-catalog-survey.yaml`
  - physical I/O naming rules and normalized signal list derived from device classification
- `survey-answers/sampling-domains-survey.yaml`
  - grouping of devices/signals by natural frequency and scan/polling domain
- `survey-answers/live-parameters-survey.yaml`
  - optional whitelist of logical parameters that may be changed live through `MqttParameterSub`
- `survey-answers/gateway-topology-survey.yaml`
  - optional but recommended declaration of edge gateways and their scope across subsystem/device groups
- `survey-answers/transport-architecture-survey.yaml`
  - required declaration of whether the model projects onto `moqui-device-gateway`, `moqui-plc4j`, or a hybrid architecture
- `survey-answers/main-fsm-survey.yaml`
  - per-state output function and consumed transition requests for `Main.pou`
- `survey-answers/main-rule-engine-survey.yaml`
  - predicates, transition conditions, and precedence for `MainRuleEngine.pou`

## Survey Order

The workflow should collect and persist survey answers in this order:

1. `system-decomposition-survey.yaml`
2. `elementary-device-classification-survey.yaml`
3. `signal-catalog-survey.yaml`
4. `sampling-domains-survey.yaml`
5. `live-parameters-survey.yaml`
6. `gateway-topology-survey.yaml`
7. `transport-architecture-survey.yaml`
8. `main-fsm-survey.yaml`
9. `main-rule-engine-survey.yaml`

`Main` / `MainRuleEngine` design should not start before the first four surveys
are substantially complete, because the model data is the best source of both
constraints and guided follow-up questions.

## Persistence Rule

The workflow should always be resumable from:

- `session.json`
- the seed XML inside `seed-data/`

Downstream skills should not depend on hidden memory if the on-disk session is
already complete enough.

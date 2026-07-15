# MainRuleEngine input

Use `main-rule-engine-survey.yaml` as the code-owned semantic input paired with
the topology in `main-fsm-survey.yaml`.

- Define every predicate with an Application-global `name` and IEC 61131-3 ST
  `expression`.
- Define every transition condition and unique precedence for its source state.
- For same-flow transitions, omit `request_assignments` to use the generated
  target-state request.
- For cross-flow transitions, provide `consume_condition` plus reviewed
  `request_assignments` and `apply_assignments`; generation must stop when any
  part is absent.
- Keep these expressions in the saved session and generated PLC source. Do not
  persist them in `StatusFlowTransition.conditionExpression`.

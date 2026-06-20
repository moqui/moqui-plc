## Resume Summary

This saved session captures the current hardening work on `agent-skills`
with the source-of-truth rule pushed further upstream into both seed generation
and guided questioning.

Completed in the codebase:

- upstream survey validation now distinguishes legacy `transport_scope` from
  transport-routing `transport_projection`
- `plc4j_connections` are now modeled explicitly in
  `transport-architecture-survey.yaml`
- `plc4j`-scoped signals must define `plc4j_query`
- `render_seed_from_surveys.py` now generates:
  - `DeviceConnection`
  - direct `DeviceRequest` / `DeviceRequestItem` rows for `moqui-plc4j`
  - gateway log/live requests only when gateway projection is actually required
- a canonical atomic-component library now exists for:
  - `Actuator`
  - `ActuatorGroup`
  - `Axis`
  - `AxisGroup`
  - `ProcessPid`
  - `SignalMgmt`
- the atomic-component library classifies parameters into:
  - structural identity
  - contextual signals
  - recipe/config parameters
  - runtime status parameters
- a cloneable atomic-component renderer now generates deterministic:
  - `Device`
  - `PhysicalDevice`
  - `ParameterDef`
  - `Parameter`
  - optional `DeviceConfig` / `DeviceRuleSet` / `DeviceRule`
- survey-driven seed generation now instantiates canonical logical parameters
  from the atomic-component library instead of inventing them ad hoc
- model-driven guided questions now derive the next chat questions from:
  - saved surveys
  - missing constraints
  - atomic-component expectations
  and avoid asking again for logical parameters already fixed by the chosen
  component model

Latest verification:

- `python3 -m unittest discover -s tests -p 'test_*.py'`
- result: `Ran 13 tests ... OK`

Current saved-state interpretation:

- upstream/source-of-truth hardening for surveys and seed generation is in a
  strong state
- the next major gap is downstream verification of generated PLC FSM artifacts
  against the reviewed seed and atomic-component library

Next recommended pass:

1. Extend the guided surveys for richer `plc4j` addressing patterns beyond the
   single-domain connection case.
2. Feed the same source-of-truth discipline into `moqui-plc-designer` and
   `moqui-device-config-designer`.
3. Add explicit cross-checks between generated `Main` / `MainRuleEngine`
   artifacts and the reviewed seed XML plus atomic-component library.

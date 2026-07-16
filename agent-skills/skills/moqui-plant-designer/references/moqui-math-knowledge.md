# moqui-math knowledge

Load this reference when a task involves parameters, numerical models, graphs,
paths, trajectories or mathematical provenance. Verify exact fields in
`../moqui-math/entity/MathEntities.xml`; this is a navigation and semantics
guide, not a substitute for the entity model.

## Role

`moqui-math` supplies reusable mathematical identity and history independently
from any device. `moqui-device` binds those mathematical objects to equipment.
This Math/Device duality lets one model describe specification, realization and
observed evidence without embedding numerical structures in PLC-specific data.

## Core parameter model

- `ParameterDef` defines type, purpose, grouping/classification, permission,
  unit family, constraints, priority, code, name and default semantics.
- `Parameter` is a concrete value owned through its bindings. It may hold a
  numeric, symbolic or enum value and may override unit/alias/sequence.
- `ParameterLog` is the append-oriented observation history, keyed by parameter
  and observation/sequence. It is the architectural analogy for turning
  `StatusFlowStack` into state history plus push-down memory.
- A recipe contains configurable values. Actual durations, measured feedback
  and runtime observations belong in state/log data, not recipe configuration.

## Model families

The entity model includes vectors, matrices, tensors, coordinate systems,
transformations and operands; approximate functions and samples; model
definitions, identifications, contents, runs, events, performance and data;
category-theory structures; graphs; meshes; parametric paths; and trajectories
with points, runs and statistics.

Use `Graph` entities for relationship/topology knowledge where appropriate.
Use a trajectory for a continuous, evolving path through state space. A DES is
represented by stable discrete states and event/condition-driven transitions in
Moqui StatusFlow; do not confuse trajectory samples with FSM states.

## Working rules

- Reuse a `ParameterDef` when semantics truly match; create a device-bound
  `Parameter` for each concrete instance/value.
- Preserve units, bounds and provenance from approved source material.
- Do not place IEC access syntax such as `dev.` in parameter names or aliases.
- DataDocuments/DataFeeds and embeddings are searchable projections of these
  normalized authoritative records, never a competing source of truth.
- Inspect current XML relationships before generating seed because entity
  names and required fields may evolve.

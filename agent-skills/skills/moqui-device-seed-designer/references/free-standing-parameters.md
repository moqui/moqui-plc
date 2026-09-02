# Free-standing ParameterDef/Parameter

## The gap

`render_seed_from_surveys.py` mints `moqui.math.ParameterDef` +
`moqui.math.Parameter` rows from exactly two places:

- `append_atomic_component_parameters()` — one full field set per atomic
  component instance (`Actuator`, `ProcessPid`, ...), driven by
  `atomic-component-library.json`.
- the `signals` loop in `render_seed()` — one ParameterDef/Parameter pair per
  row in `signal-catalog-survey.yaml`.

There is no third path. A value that is neither a physical I/O signal nor a
field of an atomic component's fixed surface — a supervisory alarm
threshold consumed only by `MainRuleEngine`, a site-specific tuning constant
that lives above the device level — has nowhere to go.

## The accepted workaround

Model it as a signal-catalog row anyway, with two deliberate compromises,
both of which must be called out in that row's `notes`:

1. **`device_id`** must be an elementary device (the seed-designer validator
   rejects the root DeviceGroup as a signal owner), even though the value is
   conceptually supervisory, not owned by that device. Pick the elementary
   device that most plausibly "owns" the value in the FSM's domain language,
   and say in `notes` that this is a placement of convenience, not a claim
   about physical ownership.
2. **`direction`** (and therefore `purpose_enum_id`, which is derived purely
   from direction — `input` → `PpFeedback`, `output` → `PpControl`) has no
   "configuration" option. Pick `input`/`PpFeedback` as the closer fit for a
   value something else *reads*, and say so in `notes`. Do not let this
   silently read as "this is wired sensor feedback" to a future reader.

Naming caveat: avoid double-capital fragments in the signal's `signal_name`
if the field will be flattened with a device-name prefix downstream (see
`moqui-plc-designer`'s Gotchas on field flattening). `to_upper_camel()`'s
tokenizer treats a run of capitals followed by `[A-Z][a-z]` unpredictably —
prefer `levelLowLowThreshold` over `levelLLThreshold` to get a name you can
predict without reading the tokenizer regex.

Keep the value **out of the sampling domain's `signals` list** unless you
actually want a gateway/plc4j monitoring `DeviceRequest` generated for it —
domain membership is what triggers that, independent of the signal catalog
entry itself.

The tuned value itself still belongs in a `DeviceConfig`/`DeviceRuleSet`, not
in this base seed Parameter — same rule as for atomic-component fields (see
`moqui-plc-designer`'s Gotchas on why the recipe layer is mandatory for any
non-default value).

## What this does not solve

- The seed reads, to anyone who doesn't already know this convention, as if
  the value were a real physical/feedback signal. There is no schema-level
  marker distinguishing "signal-catalog row standing in for a free
  ParameterDef" from a genuine wired input.
- If a future generator change starts deriving anything from
  `purpose_enum_id == PpFeedback` again (the same class of bug fixed in
  `infer_process_pid_fields()`), a value modeled this way is a candidate for
  the same kind of false match. Keep this workaround's parameter names
  distinctive enough that they won't plausibly collide with a real
  `Feedback`/`Setpoint` field on the same device.

This is a documented workaround for a real tooling gap, not a recommended
long-term pattern. If your session needs more than one or two of these,
that's a signal the seed model deserves a first-class "supervisory
parameter" concept — raise it rather than accumulating workarounds.

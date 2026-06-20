Helper scripts for recipe generation.

Canonical PLC source repository:

- [moqui/moqui-plc](https://github.com/moqui/moqui-plc)

Current script:

- `render_recipe_candidates.py`
  - reads a `DeviceFacade.dut`
  - derives all eligible top-level recipe variables
  - derives all eligible recipe fields for instantiated atomic FBs
  - excludes feedback fields
  - uses the fixed per-FB field catalog documented by the skill
  - prints candidate `dev.path:=value` lines
  - treats a recipe as a flat assignment list, not as a richer domain format
  - if `--session-dir` is provided, writes by default into `generated-recipes/` and updates `session.json`

Example:

```bash
python3 scripts/render_recipe_candidates.py /path/to/DeviceFacade.dut

python3 scripts/render_recipe_candidates.py \
  /path/to/DeviceFacade.dut \
  --session-dir ../../output/sessions/demo-plant-session
```

The generated output is intentionally simple:

```text
dev.paramName:=value
dev.fbInstance.someField:=value
```

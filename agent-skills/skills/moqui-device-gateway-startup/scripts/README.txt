Helper scripts for moqui-device-gateway-startup.

Current scripts:

- `render_gateway_startup_guide.py`
  - reads a reviewed seed XML or a saved session workspace
  - discovers modeled gateways, scoped PLC/controller devices, and gateway-routed
    `DeviceRequest` rows
  - emits a Markdown startup guide with concrete IDs and commands
  - reports structural blockers directly in the generated guide
  - if `--session-dir` is provided, writes by default into
    `generated-config/gateway-startup-guide.md` and updates `session.json`

Example:

```bash
python3 scripts/render_gateway_startup_guide.py \
  --seed ../../output/sessions/demo-plant-session/seed-data/reviewed-seed.xml \
  --output /tmp/gateway-startup-guide.md

python3 scripts/render_gateway_startup_guide.py \
  --session-dir ../../output/sessions/demo-plant-session
```

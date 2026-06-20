Helper scripts for moqui-plc-config.

Current scripts:

- `render_moqui_conf_checklist.py`
  - renders a review checklist for `MoquiConf.gvl`
  - follows the same section order as the skill
  - skips MQTT questions when exposure mode is `opcua` or `none`
  - can also omit the Modbus subsection when it does not apply
  - if `--session-dir` is provided, writes by default into `generated-config/` and updates `session.json`

Examples:

```bash
python3 scripts/render_moqui_conf_checklist.py --exposure-mode opcua --fieldbus other
```

```bash
python3 scripts/render_moqui_conf_checklist.py \
  --exposure-mode both \
  --fieldbus modbus \
  --output /tmp/moqui-conf-checklist.md
```

```bash
python3 scripts/render_moqui_conf_checklist.py \
  --exposure-mode opcua \
  --fieldbus other \
  --session-dir ../../output/sessions/demo-plant-session
```

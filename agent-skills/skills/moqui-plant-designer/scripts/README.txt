Helper scripts for moqui-plant-designer.

Dependency note:

- install Python dependencies with `python3 -m pip install -r requirements.txt`
- `validate_upstream_surveys.py` now requires `PyYAML` and parses the survey
  files with a real YAML parser instead of regex extraction

Current scripts:

- `init_session.py`
  - creates a new saved-session workspace
  - bootstraps `session.json`
  - creates the standard subdirectories

- `render_guided_questions.py`
  - reads the current surveys plus the atomic-component library
  - determines the first incomplete engineering stage
  - writes targeted questions for that stage into `notes/guided-questions.md`
  - avoids asking for logical FB parameters that are already implied by the selected atomic component model

- `validate_upstream_surveys.py`
  - validates that the upstream engineering surveys are materially complete before seed or PLC generation
  - checks:
    - system decomposition
    - elementary device classification
    - signal catalog
    - sampling domains
    - transport architecture
  - important transport-specific constraints:
    - `transport_scope` stays available for the user's own semantic grouping
    - `transport_projection` is the field used to route a domain toward `gateway`, `plc4j`, or `both`
    - `plc4j`-scoped domains must be covered by explicit `plc4j_connections`
    - `plc4j`-scoped signals must define `plc4j_query`

- `export_session_bundle.py`
  - exports a saved session as a zip archive
  - writes a JSON manifest with file checksums

Example:

```bash
python3 scripts/init_session.py plant-demo-001

python3 scripts/render_guided_questions.py \
  ../../output/sessions/plant-demo-001

python3 scripts/export_session_bundle.py \
  ../../output/sessions/plant-demo-001

python3 scripts/validate_upstream_surveys.py \
  ../../output/sessions/plant-demo-001
```
render_engineering_dossier.py
  Renders the approved surveys as a Markdown engineering dossier. With
  --work-effort-id it also emits optional WikiSpace/WikiPage/WikiPageWorkEffort
  seed data for an existing HiveMind project.

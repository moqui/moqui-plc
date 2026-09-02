# Generator fix log

Three real bugs in `render_device_catalog_from_seed.py` (duplicate
`DeviceFacade.dut` fields, `infer_process_pid_fields()` mis-wiring
`feedback`/`setpoint`, hardcoded `clock100ms`), one gap in
`validate_generated_plc_against_seed.py` (`--allow-logical-root` missing),
and a component-name normalization mismatch between
`render_statusflow_templates.py` and `render_device_catalog_from_seed.py`
were found while generating this Application, fixed at the skill/script
level, and covered by a new regression fixture
(`agent-skills/tests/fixtures/process-pid-valid/`, exercised by
`test_process_pid_fixture_has_no_duplicate_fields_and_correct_wiring` in
`agent-skills/tests/test_skill_regressions.py`).

`generated-plc/` in this session was regenerated from scratch after the
fixes (`render_codesys_applications.py --session-dir ...`, no manual
patching). The manual reconciliation notes previously embedded as comments
in `DeviceFacade.dut`/`DeviceManager.pou` are gone because the root causes
are now fixed upstream, not because the notes were deleted without a fix.

Full regression suite: `python -m unittest discover -s tests -p 'test_*.py'`
from `agent-skills/` — 27 tests, all passing.

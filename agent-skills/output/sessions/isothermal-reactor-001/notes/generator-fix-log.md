# Generator fix log

This session (a second, independent ProcessPid Application, distinct from
`tank-level-control-001`) exercised a code path the first one never used:
a manual fault-acknowledge recovery policy (`dev.faultAck`) instead of
auto-clear. That surfaced a fourth real generator bug, same family as the
three fixed for `tank-level-control-001`: two independently-implemented
copies of `render_state_request_declarations()` (one in
`render_device_catalog_from_seed.py`, one in `render_statusflow_templates.py`)
reserved a different name for the same "extra" state-request field
(`resetRequest` vs `faultAck`). Since `render_codesys_applications.py`
assembles `DeviceFacade.dut` from the former and `MainRuleEngine.pou` from
the latter, any FSM survey using `dev.faultAck` produced a
`MainRuleEngine.pou` that assigned a field `DeviceFacade.dut` never
declared -- caught immediately by `render_codesys_applications.py`'s own
orchestration validation, not silently.

Fixed by aligning both functions on `faultAck`. Covered by a new regression
fixture (`tests/fixtures/manual-fault-ack-valid/`) and test
(`test_manual_fault_ack_fixture_declares_and_wires_faultAck`). Full suite:
28 tests, all passing. `tank-level-control-001` was regenerated afterward
and re-verified unaffected (it never used `faultAck`).

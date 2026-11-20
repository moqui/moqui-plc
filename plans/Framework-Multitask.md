# Plan: framework structure and IEC 61131-3 fixes

Status: 2026-11-20. The architecture is confirmed and the fixes of section 3 are in the canonical source and in
every projection (CODESYS 3.5, CODESYS 4, SIMATIC AX, IoT firmware). Sections 4 and 5 are the remaining work.

## 1. Decisions

1. **Standard IEC 61131-3, no OOP.** No METHOD, PROPERTY, INTERFACE, EXTENDS, `THIS`, `FB_init`, `__NEW`.
   FUNCTION, FUNCTION_BLOCK, PROGRAM, STRUCT, ENUM, UNION, VAR_IN_OUT and global variable lists remain. The CODESYS
   extensions already in use (`__XADD`, `REF=`, `__ISVALIDREF`, `ADR`) stay confined to few places, each with an
   equivalent in every projection.
2. **One CODESYS Application is one IEC 61131-3 RESOURCE**, with its own copy of the framework, its runtime
   components, tasks and device tree. Independent machines are distinct Applications or PLCs.
3. **The tasks of one Application are parts of one machine:** an error in one stops all of them. They run in one
   task group with fixed core binding (`IEC-Tasks`, Fixed pinned, on CODESYS Control Win V3 x64), so the Application
   keeps single-core semantics and needs no barrier between its tasks.
4. **The instance is the context.** A function block keeps its context in its retained variables; no context stack
   is needed. The task context is the startup PROGRAM of the component and its variables.
5. **Coordinated stop between Applications is out of scope for now** (network variables, a supervisor and similar
   options remain possible).

## 2. Logging rules adopted

- Blocks log events, not states: a state change, the rising edge of a fault and its end, a recipe loaded. The
  code generators of `.agents/skills/moqui-plc-designer` follow the same rule.
- Every call to a `LoggerFacade` passes `level`: function block inputs are retained.
- The facade's rate limit (`defaultLogMaxEventsPerWindow`) is a safety net against messages written at every cycle;
  a bounded burst (the `ParameterLogger` snapshot) sets `maxEventsPerWindow := 0`.
- `logEventDate` is UTC; the generated `logEventId` is `loggerName-<UTC ms>-<source slot>-<event count>`.

## 3. Fixed

| Id | Where | Defect | Fix |
|---|---|---|---|
| S1 | `MoquiStart` | `autoReset` written by the framework: a second writer of a supervision signal | The framework only reads it; the retry uses its own `retryReset` |
| S2 | `MoquiStart` | `retryCount` reset at every retry: `maxRetryCount` had no effect | Reset only by a supervision reset or a completed run |
| S3 | `MoquiStart` | `configMgmt` and `main` both wrote `ec.error` | `configError`, `mainError`; one writer at the end of the cycle |
| S5 | `MoquiConf` | Retry comment named a nonexistent flag | Comment corrected |
| L1 | `LoggerFacade` | Duplicate `logEventId` | `loggerName-<ms>-<slot>-<count>` (`nowMillis`) |
| L2 | `LoggerFacade` callers | Retained `level`: a message without `level` inherited the previous one | Explicit `level` everywhere |
| L3 | `LogDispatcher` | `batchLimit` halved and never restored | Restored after a successful publish |
| L4 | `LogDispatcher` | A DUP resend rebuilt a different batch | The same batch is resent unchanged |
| L6 | `LoggerFacade` | Alternating per-cycle messages defeated the repetition summary (log flood) | Events on edges in the blocks; rate limit in the facade |
| D1 | `mantle-hvac DeviceManager` | Valve `enable` was the pump's handshake request | `enable := pump.isEnabled` (new `Actuator` outputs `isEnabled`, `isDisabled`) |
| D2 | `ProcessPid` | `deviationInversion` was display only: reverse acting loops could not be controlled | PID inputs swapped; the cold glycol valve passes `deviationInversion := TRUE` |
| D3 | `ProcessPid` | `RAMP_REAL` timebase equal to `tickTime` | `timebase := T#1S` |
| D5 | `Actuator` | State and fault logs at every cycle | Logged on change; "Fault cleared." |
| D7 | `DeviceConfigMgmt` | A persistent error reloaded the recipes in a loop | Stable `Error` state; a `reset` rising edge starts again |
| D8, D9 | `LevelCtrlStatusMgr`, `EdgeTrigStatusMgr` | Stuck in Aborting; `errorId` alternating | Timeout also in Aborting, with its own budget; `errorId` set once on entry to Error |
| D10 | `ActuatorGroup` | Fixed `[0..7]` points; a faulted actuator counted as running | `ACTUATOR_GROUP_MAX_SIZE`; faulted actuators excluded and stopped |
| D11 | `AirDistributionController` | Not really make-before-break | The old damper is disabled after the new one is enabled (`HvacTestSuite` scenarios 25-27 updated) |
| G1 | `SignalOutputAction` | `OnPhaseStop = 3` overlapped two bits | Distinct bits: 1, 2, 4, 8 |
| G2 | `SignalMgmt` | `error` never cleared | Cleared at Reset; cumulative output logged on change |
| G3-G5 | `NetworkDiagnostics` | First module skipped, null pointer, `error` always FALSE | Loop from the first module with null check; real error |
| M1 | `Axis` | `axisEnable` used both as handshake and as level | Level input; new `axisId` for the logger name |
| M2 | `AxisGroup` | A new target with the same command was ignored | Check states start the next move (stop-and-go waypoints) |
| M3, M4 | `Axis` | Stop retriggered; stuck in WaitReset | Stop held while `cmd = Stop`; a failed `MC_Reset` returns to Error |
| M5 | `AxisGroup` | No `MC_GroupDisable` | Added on the disable path |
| M6 | `Axis`, `AxisGroup` | Logger names, levels, typo | Corrected |
| U1 | word/real conversions | Numeric conversion instead of bit reinterpretation | `RealBits`, `LongRealBits` unions; symmetric word order |
| U2 | `trim` | Characters parsed as numbers; `MID` argument order | Compared as text; `MID(STR, LEN, POS)` |
| U3 | `nowTimestamp` | Local time, read by the gateway as UTC | UTC |
| U5 | `MeanFilter` | REAL drift of the running sums | Sums recomputed once per window |
| H1 | `mantle-hvac Main` | `lastStatus` overwritten during a Drying thermal override | Kept as Drying for the whole override |
| H2 | `MainRuleEngine` | UDINT underflow of `processRemainingDuration` | Saturated at 0 |

Not defects: D4 (the recipes set `tickTime` to the clock period, `T#100ms`), L5 (`LogDispatcher` checks
`__ISVALIDREF` before using a registered buffer).

Validation, 2026-11-20: CODESYS 3.5 SP22 (axis, group, pick and place and log suites on Control Win; live MQTT log
and parameter write through Artemis), CODESYS 4 (every POU compiled), SIMATIC AX (process and motion profiles, s7
and llvm), IoT firmware (host runner with and without sanitizers, 32 HVAC scenarios).

## 4. Open

| Id | Where | Item |
|---|---|---|
| S4 | `MoquiStart` | `InputSignalUpdate`/`OutputSignalUpdate` are commented out; select simulation with a configuration flag |
| D6 | `processMotorStarterInData` | Contactor fault without command/feedback discrepancy (the function is not used today) |
| M2b | `AxisGroup` | True blending: two move instances per type used alternately, fed from a waypoint queue with a `BufferMode` blending mode |
| U4 | JSON log payload | ISO-8601 UTC with milliseconds instead of `DT#` seconds (the gateway already accepts RFC 3339) |
| Q1 | `MqttParameterSub` | Writes `dev.*` from the MQTT task: a mailbox applied by the control task |
| T1 | `mantle-hvac TestSuite` | Still wires a valve to the pump request (old pattern) |
| E1 | `ec` | `isPrimary`, `heartbeat`, `trjDynamicSlowdown*`, `abortCurrentTrajectory` unused by the framework |
| X1 | CODESYS 3.5 project | `RealBits`, `nowMillis` sit in the `device` folder, `ParameterLogger` in `org/moqui/device`, the PnP robot FB is named `TestTripodRobot`; `MqttParameterPub` lacks the two reset calls of commit 9501e7d |

## 5. Folder restructure (after the fixes)

mr-moqui style: no Java paths `src/main/org/moqui`, components grouped by set under `runtime/components/`, a README
for each significant folder, runtime configuration separate from the framework.

| Today | Proposed |
|---|---|
| `iec61131/configuration.st` | `iec61131/moqui/runtime/conf/configuration.st` |
| `framework/src/main/org/moqui/<pkg>/` | `framework/src/<pkg>/` |
| `framework/src/main/resources/MoquiConf.st` | `framework/conf/MoquiConf.st` |
| `framework/src/test/context`, `device` | `framework/test/` |
| `framework/src/test/axis`, `pnp`, `robot-arm` | `runtime/components/test/<name>/` |
| `runtime/component/mantle-udm` | `runtime/components/base/mantle-udm` |
| `runtime/component/mantle-hvac/...` | `runtime/components/addon/mantle-hvac/src/`, `src/device/`, `src/json/`, `data/`, `test/` |
| (new) | `runtime/components/dev/template/`, a component template for the generator |

To update together, since they contain the current paths: the conversion scripts (`convert-iec61131-to-ax.py`,
`convert-runtime-to-c.py`, `convert-iec61131-to-codesys4.py`, `prepare-ax-process-build.py`,
`check-motion-overrides.py`, `export-codesys.py`, the recipe exporters and `scripts/tests/`), the mirrored
projections (`simatic-ax/src`, `iot-firmware`, `codesys-v4`), `.agents/skills/*`, `.agents/tests` and
`codegen/seed-designer`. Historical sessions under `codegen/sessions/` are not rewritten.

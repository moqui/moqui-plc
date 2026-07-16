# Resume summary — Moqui Industrial HVAC E2E

## Resume protocol

On a new computer or in a new agent context:

1. Open `session.json` in this directory.
2. Read `notes/project-architecture-context.md` completely.
3. Read `notes/conversation-history.md` and `notes/e2e-test-log.md`.
4. Verify the current checkouts before relying on paths or signatures.
5. Continue from **Immediate next action** below. Do not restart the architecture analysis.

## Current objective

Complete an end-to-end HVAC demonstration using only the running application
components below, with PostgreSQL retained as the hidden Moqui-owned database:

- `moqui-plc` on CODESYS Control Win x64
- `moqui-device-gateway`
- ActiveMQ Artemis from `moqui-deploy/industrial`
- Mosquitto CLI as an independent MQTT observer

The defrost/dripping experiment was explicitly cancelled and was neither
implemented nor committed.

## Immediate next action

Inbound transport and deserialization have passed. Update the CODESYS
projectarchive with the corrected executable HVAC `JsonToParametersMapper`,
reload the Application and keep it in `RUN` against broker `127.0.0.1:1883`.
Set one target DeviceFacade value to a distinguishable value, then invoke:

```text
POST http://localhost:8081/api/device-request/run/HVAC_DEMO_LiveParametersWrite
```

Expected result: REST status `completed`, `rowCount=20`, twenty MQTT v5 messages
and all 20 approved values applied to DeviceFacade with no parser error.

## Important runtime semantics

- `JsonToParametersMapper` is now the executable 20-field HVAC inbound
  whitelist. `ParametersToJsonMapper` is documentation-only and
  `MqttParameterPub` defaults to disabled. It is reserved for optional
  peer-PLC parameter replication in a developer-defined redundancy strategy;
  telemetry belongs to `LogDispatcher`.
- `mainInitPending` is initialized `TRUE` and is cleared only when
  `MoquiStart` reaches its `Run` branch and makes the first call to `main(...)`.
  It staying `TRUE` in the last screenshot was consistent with MoquiStart not
  actually being scheduled in the simulator.
- The HVAC IEC source now contains an application `ParameterLogger` called as
  `logParameters()` immediately after `deviceManager()`. It uses external
  `clks.clock1minute` to emit a post-update snapshot of the 29 numeric
  Parameters already modeled in `HVACDemoData.xml`. Physical signal logging
  remains in `InputSignalUpdate` and `OutputSignalUpdate`.
- PLC log identity is encoded without changing `LogEvent`: `loggerName` is the
  exact `Device.deviceId`; empty `source` means `DeviceLog`, otherwise `source`
  is the exact existing `Parameter.parameterId` and means `ParameterLog`. The
  gateway no longer concatenates fields or auto-creates missing Parameters.
- HVAC thermostat control is separate from absolute limits. The three target
  trees compute `tempAboveSetpointBand`/`tempBelowSetpointBand`; normal Cooling
  and Heating use `tempSetpoint +/- tempHysteresis`, while `tempMin`/`tempMax`
  remain absolute-limit predicates. The `T=tempMax` regression passes, the
  skill suite has 26 passing tests, and Simatic AX builds with 0 errors on S7
  and LLVM. No recipe duration was invented.

## Authoritative files in this versioned session

- `seed-data/HVACDemoData.xml`: HVAC seed snapshot used by the test.

No file in this session replaces the current repository checkout. PLC/config
source snapshots and ZIP exports are deliberately local-only; inspect current
tracked sources and use this session to recover decisions and test state.

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

The last CODESYS screenshot showed the application in `SIMULAT` mode and only a
test task visible in Task Configuration. The PLC had no TCP connection to
Artemis port 1883.

The developer must:

1. logout from CODESYS;
2. disable `Online -> Simulation` so the red `SIMULAT` indicator disappears;
3. select the local `CODESYS Control Win V3 x64` runtime;
4. add/schedule program calls for `MoquiStart`, `LogDispatcher` and
   `MqttParameterSub`;
5. use broker `192.168.101.221:1883`, MQTT v5, and resolve credentials from the
   local deployment environment (never from this versioned session);
6. set `liveParamsSubTopic` to `moqui/hvac-demo/parameters/live`;
7. login, download, start, and verify `RUN` without `SIMULAT`.

After that, verify that `CODESYSControlService` owns an established TCP socket
to port 1883, then invoke:

```text
POST http://localhost:8081/api/device-request/run/HVAC_DEMO_LiveParametersWrite
```

Expected result: REST status `completed`, `rowCount=20`, and twenty MQTT v5
messages on `moqui/hvac-demo/parameters/live`.

## Important runtime semantics

- `JsonToParametersMapper` is intentionally a documentation/no-op template.
  Receipt and parsing can be proven through `MqttParameterSub`, but values will
  not be written into `dev` until an Application-specific whitelist mapper is
  generated or inserted for the demo.
- `MqttParameterPub` is a separate program/task. It is required for the later
  PLC-to-MQTT parameter-publication test.
- `mainInitPending` is initialized `TRUE` and is cleared only when
  `MoquiStart` reaches its `Run` branch and makes the first call to `main(...)`.
  It staying `TRUE` in the last screenshot was consistent with MoquiStart not
  actually being scheduled in the simulator.

## Authoritative files in this versioned session

- `seed-data/HVACDemoData.xml`: HVAC seed snapshot used by the test.

No file in this session replaces the current repository checkout. PLC/config
source snapshots and ZIP exports are deliberately local-only; inspect current
tracked sources and use this session to recover decisions and test state.

# Live test runbook: PLC logging pipeline and MQTT ownership

Audience: a Claude agent on the developer's Windows PC, with a shell
(PowerShell or Git Bash), Docker Desktop, Mosquitto clients, CODESYS
Development System V3.5 SP21 and CODESYS Control Win V3 x64.

Goal: verify live the redesign of the moqui-plc logging pipeline and of the
MQTT connection ownership (session note 16 of `conversation-history.md`). Until
now it has only been compiled (CODESYS 4, all tasks, 0 errors) and unit-tested
in the IoT firmware host tests. Nothing has run on a PLC runtime yet.

## 0. Rules for this session

- Talk to the developer in Italian. Write notes, code and docs in English.
- This runbook is a test plan, not an authorization to change sources, commit
  or push. Record results; propose fixes and wait for the developer's go-ahead.
- You cannot click in the CODESYS IDE unless a computer-use tool is available.
  For every IDE action, give the developer one short, exact instruction, then
  ask for the value or screenshot you need as evidence. Never claim a result
  you did not see.
- Credentials below are local development defaults. Never write other secrets
  into the repository or the notes.
- CODESYS Control Win without a license stops after about two hours: if the
  PLC leaves `RUN` unexpectedly, check that first.

## 1. What changed (what you are testing)

| Area | Behaviour to verify |
|---|---|
| `LogRingBuffer` | One producer (its `LoggerFacade`), one consumer (`LogDispatcher`), counters via `__XADD`. A full buffer refuses new records and counts them in `droppedCount`; nothing is overwritten. |
| `LoggerFacade` | Events below the global `ec.logMinLevel` (default `Debug`) are ignored. Equal consecutive events within `defaultLogSuppressDuration` (10 s) are counted and written once more as a summary with `repeatCount` = repetitions. |
| `LogDispatcher` | Round robin over the sources, at most `LOG_APPENDER_BATCH_SIZE` (10) records per message, released only after the broker acknowledged the publish (`logPubQoS` = QoS1). Failed batch: retried with the DUP flag up to `logPublishMaxAttempts` (3), then counted in `LogSource.discardedCount`. JSON too large: the batch is halved. A full buffer is reported by one `Warn` record "N log events dropped". |
| `MqttCommunication` | New program, task `MqttCommunicationTask` (cyclic 100 ms, priority 3). It is the only caller of `connectionFactory` and calls `MqttParameterSub`, `MqttParameterPub`, `LogDispatcher` in this order. After a connection error it disables the client and reconnects after `mqttReconnectDelay` (5 s). |
| Payload | Map of events with fixed-width keys `"001"`, `"002"`, ... Each entry has `logEventId`, `logEventDate`, `loggerName`, `source`, `level`, `marker`, `type`, `repeatCount`, `sequence` and the value field (`message`, `enumValue` or `numericValue`). |
| MQTT properties | Logs: QoS 1, retain FALSE, content type `application/json`, message expiry `logMessageExpiryInterval` = 86400 s. `paramsReDelivery` is FALSE. |
| Removed tasks | `LogDispatcherTask`, `MqttParameterSubTask`, `MqttParameterPubTask` no longer exist. |

The identity contract is unchanged: `loggerName` = exact `Device.deviceId`;
empty `source` = DeviceLog; non-empty `source` = exact `Parameter.parameterId`.

## 2. Prepare the workspace

1. In `moqui-plc`, fetch and check out `master` of `moqui-industrial/moqui-plc`
   (it also equals `mr-moqui` of `moqui/moqui-plc`). Note the commit hash in
   your test log. Read `README.md`, section "Logging and MQTT communication", and
   section "End-to-End HVAC demo".
2. Infrastructure, following the README demo sections:
   - §2 PostgreSQL and the Moqui data (needed for the database checks of T6);
   - §3 ActiveMQ Artemis (`moqui-broker1` must be `healthy`; on `/bin/bash^M`
     convert `artemis-start.sh` and `broker.xml` to LF);
   - §5 Moqui with the in-process gateway, and confirm
     `HVAC_DEMO_PlcLogSubscribe` is active.
3. Open an observer that prints the MQTT flags and v5 properties. Keep it in
   its own terminal and save its output to a file for evidence:

   ```powershell
   mosquitto_sub -h 127.0.0.1 -p 1883 -u artemis -P artemis -V mqttv5 -q 1 -d -F "%I %t %J" -t "moqui-plc" -t "moqui/hvac-demo/parameters/#" | Tee-Object -FilePath .\moqui-plc-observer.log
   ```

   `-d` prints `PUBLISH (d0, q1, r0, ...)` for each delivery, `%J` prints the
   payload with the v5 properties (content type, message expiry).

## 3. Update and check the CODESYS project

The developer ports the changes by hand into `codesys-v3/moqui.projectarchive`.
Before testing, make sure the project matches the repository.

### 3.1 Objects (sources under `iec61131/moqui/framework/src/`)

Replace: `LogEvent`, `LogSource`, `LogCmd` (only `Idle`, `Push`),
`LogRingBuffer`, `LoggerFacade`, GVL `ec`, GVL `MoquiConf`,
`MqttLogAppender`, `SerializeLogToJson`, `LogDispatcher`, `MqttParameterSub`,
`MqttParameterPub`. New: `start/MqttCommunication` (PRG),
`test/context/LogTestSuite` (PRG).

Task configuration (`iec61131/configuration.st`): remove `LogDispatcherTask`,
`MqttParameterSubTask`, `MqttParameterPubTask`; add `MqttCommunicationTask`
(cyclic `T#100ms`, priority 3, call `MqttCommunication`) and, for T2 only,
`LogTestSuiteTask` (cyclic `T#100ms`, priority 2, call `LogTestSuite`).
Structures change: the first download must be a full download, not an online
change.

### 3.2 T1 — Build

Ask the developer: **Build → Clean all**, then **Build → Build** (F11).

Pass: 0 errors. Pre-existing warnings (for example LREAL to REAL in test
suites, `no_assign` on `MqttConnectionFactory`) are acceptable; any warning
in the changed objects is a finding.

### 3.3 Source parity

With the project open, ask the developer to run **Tools → Scripting → Execute
Script File** on `moqui-plc\scripts\export-codesys.py` with a temporary target,
or run it yourself if a CODESYS scripting command line is available. Then
compare:

```powershell
git diff --no-index --stat .\iec61131 <export-target>
```

Pass: no differences in the files of §3.1. Report any other difference
without fixing it.

## 4. Tests

Write each result in `notes/e2e-test-log.md` of this session as
`T<n> PASS|FAIL|BLOCKED`, with the evidence (observer lines, online values,
SQL output). On a failure, collect evidence and continue with the independent
tests.

Useful online values (Watch list in CODESYS):

```text
connectionFactory.connected
MqttCommunication.connectionErrorCount
LogDispatcher.state / errorId / attempts / batchLimit
ec.logSourceListSize
ec.logSourceList[i].publishedCount / discardedCount / reportedDropCount
ec.logSourceList[i].logRef.writeCount / readCount / droppedCount
ec.logMinLevel
```

### T2 — LogTestSuite on the runtime

1. Tasks: only `LogTestSuiteTask` active (`StartTask` and
   `MqttCommunicationTask` disabled, or their calls excluded from the build).
2. Download, Run, wait one second.
3. Pass: `LogTestSuite.passed = TRUE` and `failedCheck = 0`. If it fails,
   report `failedCheck`: it is the number of the first failed check in source
   order.
4. Restore `StartTask` and `MqttCommunicationTask`, remove
   `LogTestSuiteTask`, download again.

### T3 — Connection and live parameter write (inbound)

Follow README §7 (`mosquitto_pub` of `HvacTempSetpoint` 23.25).

Pass: `connectionFactory.connected = TRUE`;
`MqttParameterSub.lastSubMessage` holds the payload; `dev.tempSetpoint`
becomes 23.25 within about 100 ms. Then run README §8 (gateway request,
20 messages): pass if all 20 values are applied.

### T4 — Log message format and MQTT properties

From the observer file, take one message on `moqui-plc`.

Pass:
- the payload is `{"001":{...},...}` with consecutive keys and at most 10
  entries;
- every entry has the fields listed in §1, and `sequence` increases by 1
  between consecutive entries of the same `loggerName` and message;
- the `-d` line shows `q1` and `r0`, and `d0` for normal deliveries;
- `%J` shows content type `application/json` and a message expiry close to
  86400 (if the broker or client does not report it, write "not observable",
  not PASS).

### T5 — Periodic ParameterLogger snapshot

Wait for two `clks.clock1minute` pulses.

Pass:
- per minute, 29 entries with `loggerName = HVAC_DEMO_PLC` and non-empty
  `source`, spread over 3 messages;
- the README §9 SQL query shows new `parameter_log` rows for every one of the
  29 parameters with that minute's `observed_date`:

```powershell
docker exec moqui-database psql -U moqui -d moqui -c "SELECT COUNT(DISTINCT parameter_id) FROM parameter_log WHERE observed_date > now() - interval '70 seconds';"
```

### T6 — Repetition summary

`InputSignalUpdate` logs the same DEBUG message every 10 ms
(`'Input signals acquisition and pre-processing.'`).

Pass: on the observer this message appears about twice every 10 s, not
100 times per second: one summary entry (`logEventId` ending in `-repeated`)
with `repeatCount` near 1000 (10 s / 10 ms), followed by one entry with
`repeatCount` 1 that opens the next window. Also check that `device_log` rows
arrive for it (README §9 second query).

### T7 — Level threshold

1. Online, write `ec.logMinLevel := LogLevel.Info`.
2. Pass: DEBUG entries (`level` 1) stop within 10 s; `ParameterLogger` entries
   (`level` 2) continue.
3. Write `LogLevel.Off`: nothing new is published. Restore `LogLevel.Debug`.

### T8 — Broker outage and recovery

1. `docker stop moqui-broker1` and keep it stopped for 120 s.
2. Pass during the outage:
   - `connectionFactory.connected = FALSE`;
   - `MqttCommunication.connectionErrorCount` grows (about one attempt every
     `mqttReconnectDelay`);
   - the PLC stays in `RUN` with no task overrun or watchdog;
   - `droppedCount` grows only on the sources that log every cycle;
   - `writeCount - readCount` of the `ParameterLogger` source grows by 29 per
     minute and never exceeds `LOG_MAX_SIZE`.
3. `docker start moqui-broker1`, wait until healthy.
4. Pass after recovery:
   - `connected` returns TRUE within about `mqttReconnectDelay` plus the
     broker start;
   - the queued snapshots are published;
   - `parameter_log` contains the outage minutes;
   - the first batch of each flooded source starts with a `Warn` entry
     (`level` 3, `marker` 3) "N log events dropped: log buffer full";
   - the inbound write of T3 works again.

### T9 — Message expiry with an offline consumer

This checks `logMessageExpiryInterval` (previously the logs expired after 60 s).

1. Start a persistent-session subscriber, receive some messages, then stop it
   with Ctrl+C:

   ```powershell
   mosquitto_sub -h 127.0.0.1 -p 1883 -u artemis -P artemis -V mqttv5 -q 1 -c -i expiry-check -x 3600 -t "moqui-plc" -F "%I %p"
   ```

2. Wait 3 minutes (more than the old 60 s expiry), then run the same command
   again.
3. Pass: it immediately receives the messages published during the 3 minutes,
   with `ParameterLogger` entries for each missed minute.
4. If Artemis drops them, record the broker's address and expiry
   configuration (for example `expiry-address` and `message-expiry-*`)
   before concluding.

### T10 — Optional peer-PLC publisher

1. Online: `paramsPubEnable := TRUE` for one minute.
2. Pass: `liveParamsPub` messages appear (retain TRUE, `d0`), and T3 still
   works at the same time.
3. Restore `paramsPubEnable := FALSE`.

### T11 — Optional: DUP flag on the wire

The observer shows the broker-to-client flags, not the PLC-to-broker ones. If
Npcap and Wireshark are installed, capture the loopback with filter `mqtt`
during T3 to T5.

Pass: PLC PUBLISH packets have DUP = 0. DUP = 1 appears only on a resend of a
QoS 1 log batch.

### Paths not covered live

Batch retry, discard after `logPublishMaxAttempts` and batch halving need a
failing publish or an oversized JSON. Do not force them on the developer's
project; report them as "not exercised".

## 5. Report

Finish with a short Italian summary for the developer:
- tests passed, failed and blocked, each with its evidence;
- every deviation from this runbook;
- the questions that are still open.

Update `notes/resume-summary.md` (Immediate next action) only with the
developer's consent. Do not commit.

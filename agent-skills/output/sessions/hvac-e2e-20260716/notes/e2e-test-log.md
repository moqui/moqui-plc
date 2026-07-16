# HVAC end-to-end test log

## Environment

- Date: 2026-07-16 Europe/Rome
- Host LAN address: `192.168.101.221`
- CODESYS: 3.5.21.10
- Runtime service: `CODESYS Control Win V3 - x64`
- Docker engine: 27.5.1
- Docker Compose: 2.32.4-desktop.1
- Artemis observed version: 2.44.0
- PostgreSQL image: 18.1
- Gateway: Quarkus 3.34.6 / Camel 4.18.0
- Mosquitto clients: `C:\Program Files\mosquitto`

## Running infrastructure at last check

- Artemis primary container `moqui-broker1`: host MQTT port 1883, console 8161.
- Artemis backup `moqui-broker2`: synchronized with primary.
- PostgreSQL container `moqui-database`: host `127.0.0.1:5432`, database/user
  `moqui`.
- Gateway process started with profile `local` on port 8081.
- Gateway health was `UP`; datasource and gateway identity
  `HVAC_DEMO_GATEWAY` were valid.
- Mosquitto observer PID at the time of the test listened on `moqui-plc`,
  `liveParamsPub` and `moqui/hvac-demo/parameters/#`. PIDs are ephemeral and
  must not be assumed valid after restart.

## Artemis startup

Compose file:

```text
moqui-deploy/industrial/activemq-compose.yml
```

On Windows, both mounted files were checked out as CRLF and had to be converted
locally to LF:

```text
moqui-deploy/industrial/activemq/artemis-start.sh
moqui-deploy/industrial/activemq/broker.xml
```

No commit was made for this normalization.

Verified MQTT v5 loopback with authentication and QoS 1 through Mosquitto.

## PostgreSQL and Moqui load

Started only `moqui-database` from:

```text
moqui-deploy/industrial/moqui-postgres-compose.yml
```

The runtime initially lacked `org.postgresql.xa.PGXADataSource`. Correct setup:

```powershell
.\gradlew.bat getPostgresJdbc --no-daemon
```

The resulting local runtime driver was `postgresql-42.7.13.jar`.

For a new database, data must be loaded in this order because DeviceData
references the `NOTIFICATION` email template from Mantle setup:

```text
seed-initial
seed
```

Environment used for each load:

```text
entity_ds_db_conf=postgres
entity_ds_host=127.0.0.1
entity_ds_port=5432
entity_ds_database=moqui
entity_ds_user=moqui
entity_ds_password=${MOQUI_DB_PASSWORD}
```

Verified database counts:

- HVAC devices: 16
- Parameters owned by `HVAC_DEMO_PLC`: 33
- `HVAC_DEMO_LiveParametersWrite` items: 20

## Temporary test-only database overrides

The official seed URI had no credentials and `onlyChangedParameters=Y`.
For this isolated test only, the loaded DB row was changed to:

```text
brokerUri=paho-mqtt5:?brokerUrl=tcp://localhost:1883&qos=1&userName=${MQTT_USERNAME}&password=${MQTT_PASSWORD}
onlyChangedParameters=N
```

Do not copy this secret-bearing URI back into official seed data. The proper
fix is configuration-driven credential injection/redaction in the gateway.

## Gateway startup overrides

Profile and essential process environment:

```text
QUARKUS_PROFILE=local
QUARKUS_DATASOURCE_LOG_JDBC_URL=jdbc:postgresql://localhost:5432/moqui
QUARKUS_DATASOURCE_LOG_USERNAME=moqui
QUARKUS_DATASOURCE_LOG_PASSWORD=${MOQUI_DB_PASSWORD}
MQTT_BROKER_URL=tcp://localhost:1883
GATEWAY_DEVICE_ID=HVAC_DEMO_GATEWAY
MQTT_WRITE_AFTERPUBLISH_ENABLED=false
```

The after-publish callback was disabled because Moqui runtime was intentionally
not running on port 8080. Without this override, all MQTT messages were sent but
the REST request returned 500 due to connection refusal during the callback.

## Successful gateway-to-MQTT evidence

Invocation:

```text
POST http://localhost:8081/api/device-request/run/HVAC_DEMO_LiveParametersWrite
```

Result after callback disable:

```json
{"routeId":"mqtt-write-device-request","status":"completed","rowCount":20}
```

Twenty valid messages were observed. First examples:

```json
{"parameterId":"HvacTempSetpoint","numericValue":22.000000,"tempSetpoint":22.0}
{"parameterId":"HvacTempHysteresis","numericValue":1.000000,"tempHysteresis":1.0}
{"parameterId":"HvacTempMin","numericValue":18.000000,"tempMin":18.0}
```

## Gaps discovered

1. Dynamic MQTT DeviceRequest URIs use `DeviceRequest.brokerUri` directly and
   do not inherit configured broker credentials. Official seed should not store
   secrets; gateway-side credential injection is needed.
2. REST response `publishUriList` returns the full MQTT URI including password.
   It must redact sensitive options.
3. A refused optional callback causes the command to return 500 after MQTT side
   effects have already occurred. This can cause unsafe retries/duplicate
   commands. Optional callback failure semantics must be made explicit.
4. Initial `onlyChangedParameters=Y` sends nothing when the test does not create
   a post-request EntityAuditLog row. Production behavior must be tested through
   the Moqui service update path; isolated startup requires a defined initial
   snapshot policy.
5. CODESYS acceptance is still pending. Last execution was in IDE simulation,
   with no CODESYS-owned TCP socket to Artemis.

## CODESYS acceptance checks

Required configuration:

```iecst
brokerUrl := '192.168.101.221';
brokerPort := 1883;
liveParamsSubTopic := "moqui/hvac-demo/parameters/live";
username := "${MQTT_USERNAME}";
password := "${MQTT_PASSWORD}";
```

Required observations after runtime download:

- bottom status says `RUN` and does not say `SIMULAT`;
- `CODESYSControlService` has an established TCP connection to port 1883;
- `MqttParameterSub.connectionFactory.connected = TRUE`;
- subscriber is active with no MQTT error;
- `lastSubMessage` receives each gateway payload;
- parser completes without error;
- `JsonToParametersMapper` must apply only the 20 approved HVAC keys; unknown
  envelope keys remain ignored.

Later outbound tests:

- verify `LogDispatcher` publishes LoggerFacade numeric/text batches to `moqui-plc`;
- confirm gateway persists PLC logs into the Moqui database.

`MqttParameterPub` is not part of this telemetry test. It is reserved for an
explicitly designed peer-PLC parameter-replication channel used by a redundancy
strategy and remains disabled by default.

## Inbound CODESYS result and correction

The runtime established MQTT to `127.0.0.1:1883`. Repeated gateway requests
returned `completed` with `rowCount=20`. Online CODESYS inspection proved that
`MqttParameterSub` received the first through last payloads and that
`DeserializeJsonToParameters` invoked `JsonToParametersMapper`.

The E2E test exposed a direction mistake in the application mappings. The 20
live-write fields had been placed in `ParametersToJsonMapper` while the inbound
mapper was a no-op. Source is now corrected: `JsonToParametersMapper` performs
the approved typed writes, while `ParametersToJsonMapper` is documentation-only
and its publisher defaults to disabled. Final verification awaits projectarchive
reload.

## PLC log identity correction

The outbound `LogDispatcher` message reached the gateway, but the original
payload used `loggerName=hvac`. The gateway consequently attempted to persist a
`DeviceLog` for a non-existent device. The agreed `LogEvent` persistence
contract is now explicit and implemented without changing the PLC structure:

```text
loggerName = exact moqui.device.Device.deviceId
source     = empty                         -> DeviceLog
source     = exact moqui.math.Parameter.parameterId -> ParameterLog
```

`loggerName` and `source` are identifiers, not display names or diagnostic
categories. `payloadType` remains independent: device- and parameter-scoped
events may both carry numeric, text, or enum payloads. The gateway no longer
constructs a parameter identifier by concatenating the two fields and no longer
creates an unknown parameter implicitly.

For the HVAC Application, framework/application messages now use
`HVAC_DEMO_PLC`; the periodic `ParameterLogger` uses the same device identifier
and exact IDs such as `HvacProcessMinDuration` as `source`. Standard device
blocks use their configured device identifier directly.

Gateway verification:

```text
gradlew integrationTest --tests "*PlcLogIngestIntegrationTest"
BUILD SUCCESSFUL
```

The integration scenarios verified both `DeviceLog` and `ParameterLog` routing.
The corrected IEC 61131-3 sources still require import into the CODESYS
projectarchive, compilation, download, and a final live MQTT observation.

## Manual Simatic AX and IoT firmware projection

At the developer's request, the logging changes were applied file by file to
both platform trees without running the projection scripts.

- Simatic AX now uses exact device IDs in the framework and HVAC component,
  contains its own 29-value `ParameterLogger`, and uses exact IDs in AX recipes
  and test configuration.
- IoT firmware now treats normal text events as device-scoped (`source` empty),
  provides `LoggerFacade_LogNumeric` for parameter-scoped events, and contains
  matching `ParameterLogger.c/.h` files in `components/moqui` and `src-manual`.
- The IoT ring capacity is `LOG_MAX_SIZE`; draining one MQTT batch subtracts
  only the extracted count, preserving the rest of the minute snapshot.

Verification results:

```text
apax build: S7 and LLVM compiled with 0 errors
MSVC C11 syntax check: generated and src-manual changed C files passed
python skill regressions: 25 tests passed
```

The full ESP-IDF Docker build did not start because the local machine did not
have `espressif/idf:latest` and its image download did not complete within ten
minutes. No compiler error was produced. A native ESP-IDF build remains a
platform verification item.

## HVAC thermostat-band correction

The live test proved the inbound path by applying `tempSetpoint=23.25` through
`MqttParameterSub`. It also exposed that `CivilCooling` remained in Standby at
`tempFeedback=tempMax=26`: the supervisor incorrectly used the absolute
`tempMin`/`tempMax` limits as normal thermostat thresholds.

IEC 61131-3, Simatic AX, and both maintained IoT C trees now compute explicit
`tempAboveSetpointBand` and `tempBelowSetpointBand` predicates. Cooling and
Heating start and stop on `tempSetpoint +/- tempHysteresis`; absolute limits
remain available for the exceptional Drying overrides and alarm handling.
The regression uses exactly `T=tempMax` to ensure the demo starts Cooling even
though the absolute upper limit has not been exceeded.

Verification after the change:

```text
python skill regressions: 26 tests passed
apax build: s7generic and llvm compiled with 0 errors
```

No arbitrary process duration was added to the recipes. Continuous versus
finite sequential recipe execution remains an application-level decision.

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
- `JsonToParametersMapper` does not mutate `dev` until the demo-specific mapper
  is deliberately supplied.

Later outbound tests:

- add `MqttParameterPub` task/program call;
- observe base HVAC JSON on the chosen publication topic;
- verify `LogDispatcher` publishes LoggerFacade batches to `moqui-plc`;
- confirm gateway persists PLC logs into the Moqui database.

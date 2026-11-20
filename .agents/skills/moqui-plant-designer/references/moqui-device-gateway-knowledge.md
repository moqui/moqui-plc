# moqui-device-gateway knowledge

Load this reference for field transport, startup or end-to-end testing. Verify
current behavior in `../moqui-device-gateway/README.md` and the selected
branch's protocol implementations and services.

## Runtime boundary

On `mr-moqui` the gateway is a Moqui component in Rust/Tokio that runs inside
MR-Moqui; on `main` (formerly `master`) it is a separate Java/Quarkus/Apache
Camel process reached over REST. Either way it does not own a separate domain
model: devices, requests, items and connections are the Moqui entities.

It executes model-driven MQTT v5 publish/subscribe, OPC UA read/write/subscribe,
Modbus TCP read/write/polling, file and SFTP transfer, and PLC log ingestion.
Recipe rendering and trajectory messages are moqui-device services; the gateway
only sends them.

## Principal contracts (mr-moqui)

- `moqui.device.DeviceServices.run#DeviceRequest` runs a request through the
  protocol service in its `runServiceName`:
  `moqui.device.gateway.MqttServices`, `OpcUaServices`, `ModbusServices`,
  `FileServices` or `PlcLogServices` (verb `run#DeviceRequest`). It returns
  `status`, `itemResults`, `subscriptionId`, `transferredFiles` and
  `errorMessage`.
- Content transfer: `run#DeviceRequest` with `deviceContentId` on a
  `DrtContentTransfer` request run by `FileServices`.
- Recipe export: `moqui.device.DeviceConfigServices.export#DeviceConfig`, or
  `run#DeviceRequest` on a `DrtConfigWrite` request whose `query` is the
  `DeviceRuleSet`.
- Trajectory: `moqui.device.TrajectoryPlannerServices.export#Trajectory`, one
  JSON message (`payload`) published by an MQTT write request without items.
- Stored values go through `moqui.device.gateway.InboundServices.store#Samples`
  and `store#PlcLog`; a SECA on them replaces the old after-store callback.
- The service job `start_DeviceGatewaySubscriptions` restores the subscriptions
  after a start and restarts those that lost their connection.
- PLC `LogEvent` ingestion uses persistent IDs directly: `loggerName` is an
  exact `Device.deviceId`; empty `source` routes the event to `DeviceLog`, while
  non-empty `source` is an exact existing `Parameter.parameterId` and routes to
  `ParameterLog`. Payload type does not select the target. The gateway must not
  concatenate these fields or create missing Parameters from inbound logs.

MQTT or OPC UA delivery is the responsibility boundary. Use MQTT v5 broker
persistence and delivery policy; do not invent another application-level
acknowledgement protocol. A PLC/runtime failure after transport delivery is not
reclassified as a Moqui model failure.

## Security and configuration

Official seed must not contain secrets. Resolve credentials from deployment
configuration (`usernameEnv`/`passwordEnv` in the DeviceConnection options) and
redact them from logs. Treat a URI containing username/password as sensitive.

## Known HVAC E2E findings (2026-07-16)

These are verified observations, not universal design contracts; recheck the
current gateway before fixing them:

1. Dynamic MQTT request URIs used `DeviceRequest.brokerUri` directly and did
   not inherit configured broker credentials.
2. `publishUriList` could expose sensitive URI options in a REST response.
3. An unavailable optional Moqui callback returned HTTP 500 after MQTT side
   effects had succeeded, creating duplicate-retry risk.
4. `onlyChangedParameters=Y` produced no initial payload without qualifying
   audit history; the initial-snapshot policy needs an explicit production test.

Keep these gaps distinct from the proven path: the Java gateway REST dispatch published
20 HVAC live-parameter messages through Artemis and PostgreSQL-backed request
data. CODESYS consumption/publication remained pending at that checkpoint.

## Rust branch verification (2026-10-21)

The historical HVAC findings above concern the earlier Java gateway checkpoint.
The `mr-moqui` component uses MQTT v5 acknowledgements, deployment credentials,
no REST hop or callback, device-scoped content transfers and SFTP with pinned
host keys. Test current branch behavior before applying historical workarounds.
RuSTy and IronPLC are experimental compiler openings for simple programs; they
are not required by the Rust gateway or supported full moqui-plc platforms.

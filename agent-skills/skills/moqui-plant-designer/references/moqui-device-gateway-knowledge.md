# moqui-device-gateway knowledge

Load this reference for field transport, REST dispatch, startup or end-to-end
testing. Verify current behavior in `../moqui-device-gateway/README.md`, its
Quarkus resources, Camel routes, model services and SQL.

## Runtime boundary

The gateway is an external Quarkus/Camel edge process. It prevents asynchronous
PLC traffic from occupying the Moqui runtime, but it does not own a separate
domain model. It reads the Moqui database—normally PostgreSQL or YugabyteDB—as
the persistent declaration of devices, requests, items and connections, even
when the Moqui application is hidden behind services.

It executes model-driven MQTT v5 publish/subscribe and OPC UA read/write/
subscribe routes, PLC log ingestion, recipe/config and trajectory transfer,
content transfer, discovery/startup restoration and REST dispatch.

## Principal contracts

- `POST /api/device-request/run/{requestName}` executes a gateway-side
  DeviceRequest.
- `POST /api/device-content/transfer/{requestName}` transfers modeled content.
- `POST /api/device-config/export` drives configuration/recipe export.
- Moqui wrapper services call these endpoints and optional callbacks return to
  Moqui REST services.

MQTT or OPC UA delivery is the responsibility boundary. Use MQTT v5 broker
persistence and delivery policy; do not invent another application-level
acknowledgement protocol. A PLC/runtime failure after transport delivery is not
reclassified as a Moqui model failure.

## Security and configuration

Official seed must not contain secrets. Resolve credentials from gateway/deploy
configuration and redact them from logs and REST representations. Treat a URI
containing username/password as sensitive. Authentication for gateway REST is
configured by header/token or bearer policy.

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

Keep these gaps distinct from the proven path: gateway REST dispatch published
20 HVAC live-parameter messages through Artemis and PostgreSQL-backed request
data. CODESYS consumption/publication remained pending at that checkpoint.

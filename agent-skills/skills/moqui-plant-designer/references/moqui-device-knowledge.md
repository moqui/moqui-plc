# moqui-device knowledge

Load this reference for device topology, configuration, StatusFlow projection,
seed generation or Moqui service work. Verify exact contracts in
`../moqui-device/entity/DeviceEntities.xml`, `DeviceViewEntities.xml`,
`service/moqui/device/DeviceServices.xml` and `DeviceGatewayServices.xml`.

## Role and identity

`Device` is logical/type identity; `PhysicalDevice` is an installed or software
instance. One hardware PLC CPU or one CODESYS Application is one distinct
Device/PhysicalDevice. A CODESYS Project may contain several Applications, each
with its own framework copy, runtime component, tasks and manually configured
device tree.

The model includes devices, events/content/stats/logs, physical devices,
explicit DeviceGroups and membership, connections, requests/items,
device-bound mathematical models, configurations, rule sets/rules, dashboards
and trajectory-axis bindings. Never invent obsolete `DeviceConfigSet` entities.

## Configuration and recipes

- `DeviceConfig` is an atomic reusable type-level configuration.
- `DeviceRule` binds a compatible config to one device instance.
- `DeviceRuleSet` composes the ordered multi-device recipe; rule priority is the
  recipe/export order.
- Only configurable values enter recipes. Exclude actual values and feedback.
- MQTT live updates are an explicit developer-approved subset of already
  identified device parameters. Represent the whitelist with the appropriate
  DeviceRequest/DeviceRequestItems and generate an Application-specific PLC
  mapper.

## Requests and service pattern

All protocol implementations follow the `run#DeviceRequest` interface pattern.
`moqui-device-gateway`, `moqui-plc4j` and `moqui-genicam` are symmetric
implementations selected through routing/service data.

For the gateway there are two request layers:

1. The Moqui-side wrapper belongs to the gateway Device, uses
   `DrrMoquiDeviceGateway`, calls
   `moqui.device.DeviceGatewayServices.run#GatewayDeviceRequest`, stores the
   gateway REST base URL in `brokerUri`, and names the gateway-side request in
   `query`.
2. The gateway-side request belongs to the field Device and stores MQTT/OPC UA
   transport details. The gateway re-queries request items from the shared
   Moqui database; item lists are not forwarded through the wrapper REST call.

`export#DeviceConfig` traverses RuleSet -> Rule -> Config -> Parameter and adds
the IEC `dev.` namespace only at projection time. Persistent trajectories use
the configuration/recipe route; ephemeral trajectories use the dedicated
trajectory export service.

## FSM and naming rules

Moqui StatusFlow is authoritative for UI-visible states and transition topology.
Prefer independent flat flows per system/subsystem; use nested flows only for a
real push-down requirement. PLC code owns predicates, state outputs, interlocks,
FSM stitching and invocation order. Do not alter StatusFlow entities to encode
arbitrary executable semantics.

Store `coldGlycolPump`, `tempSetpoint` and `enableTime`, never
`dev.coldGlycolPump` or `dev.tempSetpoint`. Device ownership already supplies
the namespace. DeviceGroups and memberships come from the developer and are
validated/materialized without inference.

## Seed quality gate

Before approval, validate referential order, enum/service names, compatible
config bindings, unique identifiers, explicit request item JSON names,
controller/Application boundaries and transport scope. Use the HVAC demo and
the HiveMind/cybersecurity/electrical-compliance project data as patterns, but
check current source rather than cloning assumptions.

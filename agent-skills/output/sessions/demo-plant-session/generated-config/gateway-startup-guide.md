# moqui-device-gateway first-startup guide

Source seed: `output/sessions/demo-plant-session/seed-data/reviewed-seed.xml`
Generated guide: `output/sessions/demo-plant-session/generated-config/gateway-startup-guide.md`

This guide is derived from the reviewed seed data. If a prerequisite is wrong, fix the seed/model and regenerate this guide.

## Startup blockers

- No gateway was found in DeviceGroupMember with purposeEnumId = DgmpEdgeGateway.

## Model preflight

- Verify the reviewed seed has been loaded into the Moqui-managed database used by the gateway.
- Verify the gateway identity exists as both `Device` and `PhysicalDevice`.
- Verify the gateway is a `DeviceGroupMember` with `purposeEnumId = DgmpEdgeGateway`.
- Verify each target PLC/controller is in at least one shared `DeviceGroup` with the gateway.
- Verify active startup requests use `routerEnumId = DrrMoquiDeviceGateway`.

## Useful integration tests from moqui-device-gateway

- `./gradlew test --tests '*GatewaySeededRouteIntegrationTest' -Dquarkus.profile=integration`
- `./gradlew test --tests '*GatewayDeviceGroupSubscriptionDiscoveryTest' -Dquarkus.profile=integration`
- `./gradlew test --tests '*PlcLogIngestIntegrationTest' -Dquarkus.profile=integration`

## Principle

The gateway startup procedure must stay a projection of the data model. If startup fails because scope, requests, or identities are incomplete, repair the modeled data and regenerate.

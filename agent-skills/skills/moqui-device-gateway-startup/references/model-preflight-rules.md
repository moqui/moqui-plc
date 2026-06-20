# Model Preflight Rules

Before first startup, the seed should be checked with these rules.

## Gateway identity

- at least one logical gateway must exist in the model
- the chosen gateway ID must exist as both `Device` and `PhysicalDevice`
- the chosen gateway must be a `DeviceGroupMember` with
  `purposeEnumId = DgmpEdgeGateway`

## Scope

- the gateway must belong to at least one `DeviceGroup`
- each target PLC/controller that the gateway should serve must belong to one of
  the same groups
- if a request belongs to a PLC outside the gateway scope, startup restore or
  manual execution will be rejected

## Requests

- routed startup requests must use `routerEnumId = DrrMoquiDeviceGateway`
- startup subscriptions are typically:
  - `DrtCyclic`
  - `DrtSubscribe`
  - `DrtEvent`
  - `DrtStateChange`
- control/write requests are typically `DrtWrite`
- PLC log requests are identified by `purposeEnumId = DrpLogging`; in this case
  the MQTT topic is stored in `DeviceRequest.query` and items are not required

## Live parameters

- parameters admitted for live change should be modeled before PLC and gateway
  generation
- `DeviceRequestItem.query` should carry the MQTT key used by
  `MqttParameterSub`
- if the live-parameter list is partial, the generated JSON mapping and the
  gateway-facing request catalog will also be partial

## Principle

If one of these checks fails, the remedy is to fix the model and regenerate the
derived artifacts, not to patch the gateway startup procedure manually.

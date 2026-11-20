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
- a gateway request whose PLC is outside the gateway scope is reported by the
  startup guide and refused by the gateway when `device_gateway_device_id` is
  set; fix the group membership in the model
- only members with a controller purpose (`DgmpProcessPLC`, `DgmpSafetyPLC`,
  `DgmpController`, `DgmpMotionController`, remote I/O) and membership status
  empty or `DgmsAlive` have their subscriptions restored

## Requests

- a gateway request names its protocol service in `runServiceName`:
  `moqui.device.gateway.MqttServices.run#DeviceRequest` with
  `routerEnumId = DrrMQTTBroker`; `OpcUaServices`, `ModbusServices` or
  `FileServices` with `DrrDirect`; `PlcLogServices` for PLC logs
- the service must match the endpoint (`brokerUri` or the `DeviceConnection`):
  the gateway rejects an MQTT request sent to `OpcUaServices`, for example
- startup subscriptions are typically:
  - `DrtCyclic`
  - `DrtSubscribe`
  - `DrtEvent`
  - `DrtStateChange`
- control/write requests are typically `DrtWrite`
- PLC log requests use `PlcLogServices` and `purposeEnumId = DrpLogging`; the
  MQTT topic is stored in `DeviceRequest.query` and items are not required
- the service job `start_DeviceGatewaySubscriptions` starts every active
  subscription request of the gateway after a start

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

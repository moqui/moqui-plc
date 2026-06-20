# First Startup Workflow

This guide exists for the moment in which the seed has already been reviewed
and the next objective is to prove that `moqui-device-gateway` can start from
the model without hidden manual wiring.

The intended sequence is:

1. complete upstream engineering surveys
2. generate and review the seed
3. ensure gateway identity and scope are modeled with:
   - `Device`
   - `PhysicalDevice`
   - `DeviceGroup`
   - `DeviceGroupMember`
4. ensure active gateway-routed `DeviceRequest` rows exist for the first use
   cases
5. load the reviewed seed into the Moqui-managed database
6. start PostgreSQL and the MQTT broker used by the gateway
7. start `moqui-device-gateway` with `GATEWAY_DEVICE_ID`
8. verify `/q/health/ready`
9. prove at least one modeled request path:
   - MQTT write
   - MQTT subscribe
   - PLC log ingest
   - OPC UA, if used

The gateway should never require a separate hidden list of routes. Startup
discovery must come from the modeled data.

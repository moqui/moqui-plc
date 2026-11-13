# HVAC Demo Checkpoint Workflow

Use this reference to conduct the demo conversationally. Obtain evidence for
one checkpoint before advancing to the next.

## Architecture to explain first

The demo proves two independent directions:

```text
Moqui HVAC data -> moqui-device-gateway -> Artemis MQTT -> CODESYS
CODESYS ParameterLogger -> Artemis MQTT -> moqui-device-gateway -> Moqui database
```

Mosquitto is an observer and test publisher, not the broker. `MqttParameterSub`
handles approved live updates. `LogDispatcher` handles numeric and textual log
events. `MqttParameterPub` is reserved for an explicitly designed peer-PLC
parameter-replication strategy and is not needed by this demo.

## Checkpoints

### A. Preflight

- Run `scripts/check_demo_prerequisites.py`.
- Resolve missing repositories or tools.
- Treat occupied ports as informational: a demo service may already be active.
- Confirm that the user can open CODESYS and has Control Win available.

Evidence: all required command-line and repository checks pass.

### B. Database and model

- Start the documented PostgreSQL service.
- Load `seed-initial` before regular `seed` if the database is new, then
  `moqui-device/data/HVACDemoGatewayData.xml` (demo data: broker connection and
  PLC log subscription).
- Verify the HVAC device and live request-item counts with the README queries.
- Explain any local SQL credential/request override before applying it.

Evidence: `HVAC_DEMO_PLC`, `HVAC_DEMO_GATEWAY`, and the modeled live request are
queryable from PostgreSQL.

### C. MQTT broker and observer

- Start the documented Artemis Compose project.
- Wait for the primary broker to become healthy.
- Start `mosquitto_sub` before producing test traffic.

Evidence: the primary broker is healthy and the observer remains subscribed to
both the PLC-log and HVAC live-parameter topics.

### D. Moqui with the gateway

- Start MR-Moqui with `moqui-device-gateway` installed and
  `device_gateway_device_id=HVAC_DEMO_GATEWAY`, `MQTT_USERNAME` and `MQTT_PASSWORD`
  in its environment, as documented.
- Wait for the service job `start_DeviceGatewaySubscriptions` (one minute).

Evidence: the Moqui log reports the started subscriptions and
`get#SubscriptionState` lists `HVAC_DEMO_PlcLogSubscribe`; the subscriptions come
from the modeled requests, without a hidden route list.

### E. CODESYS

Ask the user to:

1. open `codesys-v3/moqui.projectarchive`
2. connect the IDE to CODESYS Control Win
3. verify `MoquiConf` broker/topic values
4. configure the `MoquiStart` (StartTask) and `MqttCommunication`
   (MqttCommunicationTask) task calls; `MqttCommunication` calls
   `MqttParameterSub`, `MqttParameterPub` and `LogDispatcher`, which have no
   task of their own
5. disable unrelated test tasks
6. login, download, and enter Run

Evidence: the status is `RUN`, not `SIMULAT`, and
`connectionFactory.connected` is `TRUE`.

### F. Direct inbound smoke test

- Publish one documented whitelisted live parameter with `mosquitto_pub`.
- Ask the user to observe the parser and `DeviceFacade` value online.

Evidence: observer sees the message, parser completes without error, and the
expected PLC variable changes.

### G. Modeled outbound request

- Set a recognizable Moqui parameter value as documented.
- Run `moqui.device.DeviceServices.run#DeviceRequest` for
  `HVAC_DEMO_LiveParametersWrite` (Tools app, Service Run).
- Observe the MQTT messages and CODESYS variable.

Evidence: the result has `status = completed` and 20 `itemResults`, and CODESYS
applies the recognizable value.

### H. PLC return path

- Keep CODESYS running through a `clks.clock1minute` pulse.
- Observe `ParameterLogger` messages on `moqui-plc`.
- Query `parameter_log` and, where applicable, `device_log`.

Identity contract:

- empty `source`: device event; `loggerName` is exact `Device.deviceId`
- non-empty `source`: parameter event; `source` is exact
  `Parameter.parameterId`

Evidence: a recent database row matches the exact parameter ID and value sent
by CODESYS.

## Result report

Report:

- environment and date
- checkpoints A-H with pass/fail status
- last proven checkpoint
- exact blocker and relevant evidence
- any temporary local override used
- whether services were left running or stopped

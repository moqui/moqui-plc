# HVAC Demo Troubleshooting

Load this reference only after a checkpoint fails. Use the root
`moqui-plc/README.md` troubleshooting section for exact current commands.

## Broker unavailable

- Check Docker Desktop and the Artemis container health.
- Check whether port 1883 is owned by another MQTT broker.
- On Windows, inspect mounted Artemis shell/config files for CRLF problems.
- Confirm the development credentials only in local configuration.

## Gateway health down

- Verify both datasource URLs and PostgreSQL availability.
- Verify `GATEWAY_DEVICE_ID=HVAC_DEMO_GATEWAY`.
- Verify the HVAC seed exists in the database.
- Read the actual Quarkus port from startup output.

## Gateway request publishes zero rows

- Verify the exact `DeviceRequest` name and its active items.
- For the isolated first snapshot, inspect `only_changed_parameters` as
  documented.
- Do not permanently weaken normal change-detection behavior to make the demo
  appear successful.

## CODESYS receives no MQTT message

- Confirm `RUN`, not `SIMULAT`.
- Confirm Control Win owns an external MQTT connection.
- Check broker address, port, topic, credentials, and task call.
- Verify direct `mosquitto_pub` delivery before involving the gateway.

## JSON arrives but value is unchanged

- Check parser error/busy/done state.
- Verify the JSON contains a whitelisted application key, not only envelope
  fields such as `parameterId` and `numericValue`.
- Verify `JsonToParametersMapper` matches the reviewed request-item aliases.

## No PLC logs return

- Check `LogDispatcher` task execution and connection state.
- Check `clks.clock1minute` and the `ParameterLogger` call after
  `DeviceManager`.
- Distinguish device events from parameter events using the `source` contract.
- Query the correct table using the exact modeled identity.

## FSM behavior differs from the demo

- Verify the current recipe is loaded and has the documented finite demo
  duration.
- Verify feedback lies outside the thermostat hysteresis band when a Heating or
  Cooling transition is expected.
- Treat this as an application/recipe diagnostic, not as proof that MQTT failed.


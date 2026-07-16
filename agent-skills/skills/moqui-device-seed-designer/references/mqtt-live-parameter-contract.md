# MQTT live-parameter contract

After the complete device Parameter catalog is generated, ask the developer
which existing parameters may receive temporary live updates and assign one
unique `mqttKey` to each selection.

For every selected parameter the seed generator creates a
`DeviceRequestItem` whose `parameterId` references the existing device-bound
Parameter and whose `requestItemName` is the reviewed JSON key. Requests are
partitioned by owning CPU/CODESYS Application.

The gateway publishes a backward-compatible envelope containing both model
identity/value fields and the mapper key:

```json
{"parameterId":"P_TEMP_SETPOINT","numericValue":22.5,"tempSetpoint":22.5}
```

The PLC generator resolves the selected Parameter through its `ParameterDef`,
derives the IEC type and generated DeviceFacade field, and emits an
Application-specific `JsonToParametersMapper`. Unknown JSON keys remain ignored.

This uses the existing MQTT v5 delivery path and adds no PLC acknowledgement
protocol. Never whitelist feedback, status or safety-related parameters unless
the developer explicitly confirms that changing them is valid.

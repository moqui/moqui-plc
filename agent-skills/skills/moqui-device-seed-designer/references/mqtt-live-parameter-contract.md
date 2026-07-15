# MQTT live-parameter payload decision

The gateway currently serializes a request item as a generic parameter object,
for example:

```json
{"parameterId":"P_TEMP_SETPOINT","numericValue":22.5}
```

The sample PLC mapper consumes application keys, for example:

```json
{"tempSetpoint":22.5}
```

A backward-compatible candidate is to include the reviewed `requestItemName`
as an additional top-level key:

```json
{"parameterId":"P_TEMP_SETPOINT","numericValue":22.5,"tempSetpoint":22.5}
```

This is a serialization choice inside the existing MQTT v5 transport, not a
new acknowledgement protocol. Do not change gateway/runtime payloads until the
developer selects the canonical contract and its compatibility policy.

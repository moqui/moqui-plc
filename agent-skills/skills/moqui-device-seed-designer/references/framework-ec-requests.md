# Framework EC Requests

This reference captures the standard framework-facing variables exposed by
[moqui/moqui-plc](https://github.com/moqui/moqui-plc) in
`iec61131/moqui/framework/src/main/org/moqui/context/ec.gvl`.

These variables should be considered a reusable baseline for PLCs built on the
`moqui-plc` framework.

## Control-oriented fields

- `enable`
- `init`
- `reset`
- `autoReset`
- `logAppenderEnable`
- `paramsPubEnable`
- `paramsSubEnable`
- `retryTime`

## Status / monitoring fields

- `fault`
- `error`
- `commError`
- `allConfigLoaded`
- `retryCount`
- `isPrimary`
- `heartbeat`

## Suggested standard request split

### Framework status read request

Purpose:

- monitor framework health and role
- detect communication issues
- observe config-loading state and heartbeat

Typical items:

- `fault`
- `error`
- `commError`
- `allConfigLoaded`
- `isPrimary`
- `heartbeat`
- `retryCount`

### Framework control write request

Purpose:

- enable/disable the runtime
- trigger init/reset flows
- manage MQTT-side framework services
- tune retry behavior

Typical items:

- `enable`
- `init`
- `reset`
- `autoReset`
- `logAppenderEnable`
- `paramsPubEnable`
- `paramsSubEnable`
- `retryTime`

## Notes

- The request family is standard and should not be redesigned project by project
- The request names can be derived deterministically from `deviceId`
- `heartbeat` is naturally a monitoring/status signal
- `retryTime` behaves more like a configuration/control parameter than pure status
- `logAppenderEnable`, `paramsPubEnable`, and `paramsSubEnable` should be included in the standard framework control surface

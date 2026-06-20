# MoquiConf Review Template

Use this structure to summarize chosen values before editing `MoquiConf.gvl`.

## Framework

- `retryOnError` =
- `minRetryTime` =
- `maxRetryCount` =

## Logger

- `LOG_MAX_SIZE` =
- `defaultLogLevel` =
- `LOG_SOURCE_LIST_MAX_SIZE` =
- `LOG_JSON_PAYLOAD_MAX_SIZE` =
- `JSON_PAYLOAD_MAX_SIZE` =
- `LOG_APPENDER_BATCH_SIZE` =
- `logTopic` =
- `logAppenderTimeout` =
- `moquiCmdsTopic` =
- `liveParamsSubTopic` =
- `liveParamsSubTimeout` =
- `liveParamsPubTopic` =
- `liveParamsPubTimeout` =

## Communication Protocols

- `fieldbus` =

### Modbus

- `MODBUS_OVERRANGE` =
- `MODBUS_OVERFLOW` =

### MQTT

- `brokerUrl` =
- `brokerPort` =
- `webSocketUrl` =
- `clientId` =
- `username` =
- `password` =
- `sessionExpiryInterval` =
- `keepAlive` =
- `cleanSession` =
- `timeout` =
- `pingInterval` =
- `communicationMode` =
- `mqttVersion` =
- `willTopic` =
- `willMessage` =
- `willRetain` =
- `willQoS` =
- `pubPayloadFormatIndicator` =
- `paramsPubQoS` =
- `paramsPubRetain` =
- `logPubQoS` =
- `logPubRetain` =
- `subscriptionIdentifier` =
- `paramsSubQoS` =
- `paramsSubFilterMode` =

## Signal Management

- `SIGNAL_LIST_MAX_SIZE` =

## Device Config Management

- `DEVICE_CONFIG_LIST_MAX_SIZE` =
- `defaultConfigType` =
- `deviceConfigStoragePath` =
- `ACTUATOR_GROUP_MAX_SIZE` =
- `AXIS_IN_VELOCITY_TOLERANCE` =

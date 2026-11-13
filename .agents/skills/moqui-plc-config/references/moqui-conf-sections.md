# MoquiConf Sections

Source:

- [moqui/moqui-plc](https://github.com/moqui/moqui-plc)
- `iec61131/moqui/framework/src/main/resources/MoquiConf.gvl`

## 1. Framework

Key constants:

- `retryOnError`
- `minRetryTime`
- `maxRetryCount`

## 2. Logger

Key constants:

- `LOG_MAX_SIZE` (records of each LoggerFacade buffer; a full buffer refuses new records)
- `defaultLogLevel`
- `defaultLogSuppressDuration` (window of the repetition summary; `T#0S` disables it)
- `defaultLogSuppressDuplicates`
- `LOG_SOURCE_LIST_MAX_SIZE`
- `LOG_JSON_PAYLOAD_MAX_SIZE`
- `JSON_PAYLOAD_MAX_SIZE`
- `JSON_LINE_BREAK`
- `JSON_ELEMENT_LIST_MAX_SIZE`
- `LOG_APPENDER_BATCH_SIZE` (records per log MQTT message)
- `logTopic`
- `logAppenderTimeout` (UDINT, microseconds; QoS 1 includes the broker acknowledgement)
- `logPublishMaxAttempts`
- `mqttReconnectDelay`
- `moquiCmdsTopic`
- `liveParamsSubTopic`
- `liveParamsSubTimeout`
- `liveParamsPubTopic`
- `liveParamsPubTimeout`

## 3. Communication Protocols

Key constants:

- `fieldbus`

### 3a. Modbus

- `MODBUS_OVERRANGE`
- `MODBUS_OVERFLOW`

### 3b. MQTT

Connection:

- `brokerUrl`
- `brokerPort`
- `webSocketUrl`
- `clientId`
- `username`
- `password`
- `sessionExpiryInterval`
- `keepAlive`
- `cleanSession`
- `timeout`
- `pingInterval`
- `maximumPacketSize`
- `communicationMode`
- `mqttVersion`

Will message:

- `willTopic`
- `willMessage`
- `willRetain`
- `willQoS`
- `willPayloadFormatIndicator`
- `willMessageExpiryInterval`
- `willContentType`
- `willDelayInterval`

General publish:

- `pubPayloadFormatIndicator`
- `pubMessageExpiryInterval`
- `pubContentType`

Live params publish:

- `paramsPubQoS`
- `paramsPubRetain`
- `paramsReDelivery` (MQTT DUP flag: `FALSE`; never `TRUE` on a first send or with QoS 0)

Log publish:

- `logPubQoS` (`QoS1`: a batch is released only after the broker acknowledged it)
- `logPubRetain` (`FALSE`: log events are not state)
- `logMessageExpiryInterval` (seconds a log message waits on the broker for an offline gateway; 86400)

The minimum log level is not a constant: it is the global `logMinLevel` of `ec`
(default `Debug`; `Info` is advisable in production), changeable online.

Subscribe:

- `subscriptionIdentifier`
- `subNoLocalOption`
- `subRetainAsPublished`
- `subRetainHandling`
- `paramsSubQoS`
- `paramsSubFilterMode`

## 4. Signal Management

- `SIGNAL_LIST_MAX_SIZE`

## 5. Device Config Management

- `DEVICE_CONFIG_LIST_MAX_SIZE`
- `defaultConfigType`
- `deviceConfigStoragePath`
- `ACTUATOR_GROUP_MAX_SIZE`
- `AXIS_IN_VELOCITY_TOLERANCE`

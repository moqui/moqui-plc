# MoquiConf Question Flow

Use this order and conditional behavior when collecting answers.

## Step 1. Framework

Ask:

- Should the framework retry automatically on error?
- What is the minimum retry time?
- What is the maximum retry count?

## Step 2. Logger

Ask:

- What log level should be the default?
- What maximum log sizes and payload sizes are acceptable?
- What MQTT topics should be used for logs and live parameters, if MQTT is used?
- What appender timeout is acceptable?

## Step 3. Communication architecture

Ask first:

- Which fieldbus/protocol family is used internally?
- How should the PLC expose data outward?
  - MQTT
  - OPC UA
  - both
  - neither

## Step 4. Modbus subsection

Ask only if Modbus is relevant:

- Should default overrange/overflow values be kept?
- If not, what limits should be used?

## Step 5. MQTT subsection

Ask only if MQTT is selected.

If the user chooses OPC UA-only exposure, omit this section.

Ask:

- broker host/port or websocket URL
- client ID
- authentication
- keepalive / session policy
- topics for log appender and live params
- QoS / retain behavior
- last will topic/message policy
- subscribe filtering behavior

## Step 6. Signal Management

Ask:

- what maximum signal list size is required?

## Step 7. Device Config Management

Ask:

- how many device configs may be loaded?
- what is the default config type?
- where are recipe/config files stored?
- what actuator-group size is required?
- what velocity tolerance should be used?

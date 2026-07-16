#ifndef MQTT_CLIENT_H
#define MQTT_CLIENT_H

/*
 * MqttClient — application-level MQTT façade.
 *
 * Transport details are hidden behind the Platform Abstraction Layer (platform.h).
 * No ESP-IDF types appear in this header; it is fully platform-neutral.
 */

#include <stdint.h>
#include <stdbool.h>
#include "Actuator.h"
#include "MoquiConf.h"

/* Maximum payload bytes per enqueued pub message. Large enough for the full
 * HVAC live-parameter and runtime-telemetry snapshot. */
#define MQTT_PUB_PAYLOAD_MAX  (2048U)

/* A single publish request placed in the mqtt_io_task queue. */
typedef struct {
    char topic[128U];
    char payload[MQTT_PUB_PAYLOAD_MAX];
    int  qos;
} MqttPubMsg;

/*
 * Initialise the MQTT client and build device-unique topics from the MAC address.
 * brokerUri: e.g. "mqtt://host:1883".  Pass NULL to use the Kconfig compile-time default.
 * Must be called once before any other MqttClient_* function.
 */
void MqttClient_Init(const char *brokerUri);

/* Low-priority FreeRTOS task — drain the pub queue and forward to broker.
 * Started in app_main; parameter is unused. */
void MqttClient_Task(void *pvParameters);

/* Enqueue an actuator state snapshot for async publish (QoS 1). */
void MqttClient_PublishActuatorState(const Actuator *actuator);

/* Enqueue a full JSON device-status snapshot for async publish (QoS 0).
 * json must be null-terminated; truncated silently to MQTT_PUB_PAYLOAD_MAX-1. */
void MqttClient_PublishDeviceStatus(const char *json);

/* Enqueue a log event JSON to the MOQUI_LOG_TOPIC for async publish (QoS 0).
 * json must be null-terminated; truncated silently to MQTT_PUB_PAYLOAD_MAX-1. */
void MqttClient_PublishLog(const char *json);

#endif /* MQTT_CLIENT_H */

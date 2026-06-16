#include "MqttClient.h"
#include "platform.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include <string.h>
#include <stdio.h>

/* MISRA C:2012 Rule 15.5 deviation: early return used for guard clause. */

#define MQTT_QUEUE_LENGTH (10U)

/* Device-unique MQTT topics, built from MAC at init time. */
static char s_actuator_topic[80U];
static char s_status_topic[80U];
/* Log topic is global (not per-device) — defined in MoquiConf.h */
static const char *s_log_topic = MOQUI_LOG_TOPIC;

static StaticQueue_t   s_queue_buf;
static uint8_t         s_queue_storage[MQTT_QUEUE_LENGTH * sizeof(MqttPubMsg)];
static QueueHandle_t   s_pub_queue;

/* ------------------------------------------------------------------ */

void MqttClient_Init(const char *brokerUri) {
    char mac[13U]; /* 12 hex chars + NUL */
    pal_net_get_mac_str(mac, sizeof(mac));

    snprintf(s_actuator_topic, sizeof(s_actuator_topic),
             CONFIG_MOQUI_MQTT_DEVICE_TOPIC_PREFIX "/%s/actuator", mac);
    snprintf(s_status_topic, sizeof(s_status_topic),
             CONFIG_MOQUI_MQTT_DEVICE_TOPIC_PREFIX "/%s/status", mac);

    s_pub_queue = xQueueCreateStatic(MQTT_QUEUE_LENGTH, sizeof(MqttPubMsg),
                                     s_queue_storage, &s_queue_buf);

    pal_mqtt_init(brokerUri);

    printf("[I][MqttClient] Actuator topic: %s\n", s_actuator_topic);
    printf("[I][MqttClient] Status  topic : %s\n", s_status_topic);
}

/* ------------------------------------------------------------------ */

static void enqueue_msg(const char *topic, const char *payload, int qos) {
    MqttPubMsg msg;
    if (!s_pub_queue || !topic || !payload) { return; }
    strncpy(msg.topic,   topic,   sizeof(msg.topic)   - 1U);
    msg.topic[sizeof(msg.topic) - 1U] = '\0';
    strncpy(msg.payload, payload, sizeof(msg.payload) - 1U);
    msg.payload[sizeof(msg.payload) - 1U] = '\0';
    msg.qos = qos;
    /* Non-blocking: drop if full (high-priority control task must not stall). */
    (void)xQueueSend(s_pub_queue, &msg, 0U);
}

void MqttClient_PublishActuatorState(const Actuator *actuator) {
    char buf[256U];
    if (!actuator) { return; }
    snprintf(buf, sizeof(buf),
             "{\"id\":\"%s\",\"name\":\"%s\",\"status\":%d,\"enabled\":%s,\"fault\":%s}",
             actuator->actuatorId   ? actuator->actuatorId   : "",
             actuator->actuatorName ? actuator->actuatorName : "",
             (int)actuator->status,
             actuator->enable ? "true" : "false",
             actuator->fault  ? "true" : "false");
    enqueue_msg(s_actuator_topic, buf, 1);
}

void MqttClient_PublishDeviceStatus(const char *json) {
    if (!json) { return; }
    enqueue_msg(s_status_topic, json, 0);
}

void MqttClient_PublishLog(const char *json) {
    if (!json) { return; }
    enqueue_msg(s_log_topic, json, 0);
}

/* ------------------------------------------------------------------ */

void MqttClient_Task(void *pvParameters) {
    MqttPubMsg msg;
    (void)pvParameters;

    while (1) {
        /* Block up to 100 ms waiting for a message. */
        if (xQueueReceive(s_pub_queue, &msg, pdMS_TO_TICKS(100U)) == pdTRUE) {
            if (pal_mqtt_is_connected()) {
                int mid = pal_mqtt_publish(msg.topic, msg.payload, 0, msg.qos);
                if (mid < 0) {
                    printf("[W][MqttClient] Publish failed on %s, re-queuing.\n", msg.topic);
                    /* Re-enqueue once; drop on second failure to avoid stall. */
                    (void)xQueueSend(s_pub_queue, &msg, 0U);
                } else {
                    printf("[D][MqttClient] Published mid=%d topic=%s\n", mid, msg.topic);
                }
            }
            /* If not connected, message is dropped (QoS 0 approach for IoT). */
        }
        /* Yield briefly between drains to let lower-priority tasks run. */
        taskYIELD();
    }
}

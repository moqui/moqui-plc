#include "MqttParameterSub.h"
#include "MqttClient.h"
#include "platform.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include <stdatomic.h>
#include <string.h>

#define RX_QUEUE_LENGTH 10U

typedef struct {
    char payload[MQTT_PUB_PAYLOAD_MAX];
    int len;
    uint32_t generation;
} ParameterMessage;
static StaticQueue_t s_queue_buffer;
static uint8_t s_queue_storage[RX_QUEUE_LENGTH * sizeof(ParameterMessage)];
static QueueHandle_t s_queue;
static atomic_uint_least32_t s_generation;
static atomic_uint_least32_t s_dropped;

/* The network task never reads or writes the DeviceFacade. */
static void rx_callback(const char *topic, int topic_len,
                        const char *payload, int payload_len) {
    ParameterMessage msg;
    msg.generation = atomic_load(&s_generation);
    if (msg.generation == 0U || topic == NULL || payload == NULL ||
        topic_len != (int)strlen(MOQUI_LIVE_PARAMS_SUB_TOPIC) ||
        memcmp(topic, MOQUI_LIVE_PARAMS_SUB_TOPIC, (size_t)topic_len) != 0) { return; }
    if (payload_len < 0 || payload_len >= (int)sizeof(msg.payload)) {
        atomic_fetch_add(&s_dropped, 1U);
        return;
    }
    memcpy(msg.payload, payload, (size_t)payload_len);
    msg.payload[payload_len] = '\0';
    msg.len = payload_len;
    if (xQueueSend(s_queue, &msg, 0U) != pdTRUE) { atomic_fetch_add(&s_dropped, 1U); }
}

void MqttParameterSub_Update(MqttParameterSub *sub, bool paramsSubEnable) {
    ParameterMessage msg;
    if (!sub->init) {
        if (s_queue == NULL) {
            s_queue = xQueueCreateStatic(RX_QUEUE_LENGTH, sizeof(ParameterMessage),
                s_queue_storage, &s_queue_buffer);
            configASSERT(s_queue != NULL);
            pal_mqtt_set_rx_cb(rx_callback);
        }
        sub->init = true;
    }
    sub->droppedMessages = atomic_load(&s_dropped);
    if (!paramsSubEnable) {
        atomic_store(&s_generation, 0U);
        if (sub->subscribed && pal_mqtt_is_connected()) {
            (void)pal_mqtt_unsubscribe(MOQUI_LIVE_PARAMS_SUB_TOPIC);
        }
        sub->done = false;
        sub->busy = false;
        sub->error = false;
        sub->errorId = 0;
        sub->subscribed = false;
        while (xQueueReceive(s_queue, &msg, 0U) == pdTRUE) {}
        return;
    }
    if (!sub->subscribed) {
        sub->busy = true;
        if (++sub->generation == 0U) { ++sub->generation; }
        atomic_store(&s_generation, sub->generation);
        int mid = pal_mqtt_subscribe(MOQUI_LIVE_PARAMS_SUB_TOPIC, 0);
        sub->subscribed = mid >= 0;
        sub->done = sub->subscribed;
        sub->error = !sub->subscribed;
        sub->errorId = sub->error ? 1 : 0;
        sub->busy = false;
        if (!sub->subscribed) { atomic_store(&s_generation, 0U); }
    }
    /* A bounded number of commands is applied between scans. */
    for (unsigned i = 0U; i < RX_QUEUE_LENGTH; ++i) {
        if (xQueueReceive(s_queue, &msg, 0U) != pdTRUE) { break; }
        if (msg.generation == sub->generation && sub->parseFn && sub->device) {
            sub->parseFn(msg.payload, msg.len, sub->device);
        }
    }
}

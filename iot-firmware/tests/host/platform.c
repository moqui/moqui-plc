#include "platform.h"
#include "freertos/queue.h"
#include <string.h>
static PalMqttRxCb receive;
bool host_connected = true;
unsigned host_subscribes;
void host_receive(const char *topic, const char *data) {
    if (receive) { receive(topic, (int)strlen(topic), data, (int)strlen(data)); }
}
void pal_mqtt_set_rx_cb(PalMqttRxCb callback) { receive = callback; }
uint64_t pal_time_us(void) { static uint64_t t; return ++t * 10000U; }
bool pal_net_is_connected(void) { return true; }
bool pal_mqtt_is_connected(void) { return host_connected; }
int pal_mqtt_subscribe(const char *topic, int qos) { (void)topic; (void)qos; ++host_subscribes; return host_connected ? 1 : -1; }
int pal_mqtt_unsubscribe(const char *topic) { (void)topic; return 1; }
void pal_mqtt_init(const char *uri) { (void)uri; }
int pal_mqtt_publish(const char *topic, const char *payload, int len, int qos) {
    (void)topic; (void)payload; (void)len; (void)qos; return 1;
}
void pal_net_get_mac_str(char *out, size_t max) { if (max) { out[0] = '\0'; } }
QueueHandle_t xQueueCreateStatic(unsigned n, unsigned size, uint8_t *data, StaticQueue_t *q) {
    *q = (StaticQueue_t){ .mutex = PTHREAD_MUTEX_INITIALIZER, .data = data, .capacity = n, .size = size };
    return q;
}
int xQueueSend(QueueHandle_t q, const void *data, TickType_t wait) {
    (void)wait;
    pthread_mutex_lock(&q->mutex);
    int ok = q->count < q->capacity;
    if (ok) { memcpy(q->data + ((q->head + q->count) % q->capacity) * q->size, data, q->size); ++q->count; }
    pthread_mutex_unlock(&q->mutex);
    return ok;
}
int xQueueReceive(QueueHandle_t q, void *data, TickType_t wait) {
    (void)wait;
    pthread_mutex_lock(&q->mutex);
    int ok = q->count > 0;
    if (ok) { memcpy(data, q->data + q->head * q->size, q->size); q->head = (q->head + 1) % q->capacity; --q->count; }
    pthread_mutex_unlock(&q->mutex);
    return ok;
}

#include "platform.h"
#include "mqtt_client.h"
#include "esp_log.h"
#include "esp_err.h"
#include "sdkconfig.h"
#include <stdatomic.h>
#include <string.h>

#define RX_TOPIC_MAX 128U
#define RX_PAYLOAD_MAX 2048U
static esp_mqtt_client_handle_t s_client;
static atomic_bool s_connected;
static _Atomic(PalMqttRxCb) s_rx_cb;
static char s_topic[RX_TOPIC_MAX];
static char s_payload[RX_PAYLOAD_MAX];
static int s_topic_len, s_received, s_expected;

static void reset_receive(void) {
    s_topic_len = 0;
    s_received = 0;
    s_expected = 0;
}
static void mqtt_event_handler(void *args, esp_event_base_t base,
                                int32_t event_id, void *data) {
    (void)args; (void)base;
    esp_mqtt_event_handle_t ev = data;
    switch ((esp_mqtt_event_id_t)event_id) {
        case MQTT_EVENT_CONNECTED:
            atomic_store(&s_connected, true);
            reset_receive();
            break;
        case MQTT_EVENT_DISCONNECTED:
            atomic_store(&s_connected, false);
            reset_receive();
            break;
        case MQTT_EVENT_DATA: {
            if (ev == NULL) { break; }
            if (ev->current_data_offset == 0) {
                reset_receive();
                if (ev->topic == NULL || ev->topic_len <= 0 ||
                    ev->topic_len >= (int)sizeof(s_topic) ||
                    ev->total_data_len <= 0 ||
                    ev->total_data_len >= (int)sizeof(s_payload)) { break; }
                memcpy(s_topic, ev->topic, (size_t)ev->topic_len);
                s_topic_len = ev->topic_len;
                s_expected = ev->total_data_len;
            }
            if (s_expected == 0 || ev->current_data_offset != s_received ||
                ev->total_data_len != s_expected || ev->data_len < 0 ||
                ev->data_len > s_expected - s_received ||
                (ev->data == NULL && ev->data_len > 0)) {
                reset_receive();
                break;
            }
            if (ev->data_len > 0) {
                memcpy(s_payload + s_received, ev->data, (size_t)ev->data_len);
            }
            s_received += ev->data_len;
            if (s_received == s_expected) {
                s_payload[s_received] = '\0';
                PalMqttRxCb callback = atomic_load(&s_rx_cb);
                if (callback) { callback(s_topic, s_topic_len, s_payload, s_received); }
                reset_receive();
            }
            break;
        }
        case MQTT_EVENT_ERROR:
            ESP_LOGE("pal_mqtt", "MQTT error");
            break;
        default:
            break;
    }
}
void pal_mqtt_init(const char *broker_uri) {
    esp_mqtt_client_config_t cfg = {
        .broker.address.uri = broker_uri ? broker_uri : CONFIG_MOQUI_MQTT_BROKER_URI,
        .session.protocol_ver = MQTT_PROTOCOL_V_5
    };
    s_client = esp_mqtt_client_init(&cfg);
    if (!s_client) { ESP_LOGE("pal_mqtt", "MQTT initialization failed"); return; }
    ESP_ERROR_CHECK(esp_mqtt_client_register_event(s_client, ESP_EVENT_ANY_ID, mqtt_event_handler, NULL));
    ESP_ERROR_CHECK(esp_mqtt_client_start(s_client));
}
bool pal_mqtt_is_connected(void) { return atomic_load(&s_connected); }
int pal_mqtt_publish(const char *topic, const char *payload, int len, int qos) {
    if (!pal_mqtt_is_connected() || !s_client) { return -1; }
    /* Unlike publish(), enqueue() does not send synchronously on the caller. */
    return esp_mqtt_client_enqueue(s_client, topic, payload, len, qos, 0, true);
}
int pal_mqtt_subscribe(const char *topic, int qos) {
    if (!pal_mqtt_is_connected() || !s_client) { return -1; }
    return esp_mqtt_client_subscribe(s_client, topic, qos);
}
int pal_mqtt_unsubscribe(const char *topic) {
    if (!pal_mqtt_is_connected() || !s_client) { return -1; }
    return esp_mqtt_client_unsubscribe(s_client, topic);
}
void pal_mqtt_set_rx_cb(PalMqttRxCb callback) { atomic_store(&s_rx_cb, callback); }

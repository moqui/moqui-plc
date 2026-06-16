#include "platform.h"
#include "mqtt_client.h"
#include "esp_log.h"

static const char *TAG = "pal_mqtt";

static esp_mqtt_client_handle_t s_client   = NULL;
static bool                     s_connected = false;
static PalMqttRxCb              s_rx_cb    = NULL;

static void mqtt_event_handler(void *handler_args, esp_event_base_t base,
                                int32_t event_id, void *event_data) {
    (void)handler_args; (void)base;
    esp_mqtt_event_handle_t ev = (esp_mqtt_event_handle_t)event_data;

    switch ((esp_mqtt_event_id_t)event_id) {
        case MQTT_EVENT_CONNECTED:
            ESP_LOGI(TAG, "Connected.");
            s_connected = true;
            break;

        case MQTT_EVENT_DISCONNECTED:
            ESP_LOGW(TAG, "Disconnected.");
            s_connected = false;
            break;

        case MQTT_EVENT_DATA:
            if (s_rx_cb != NULL && ev != NULL) {
                s_rx_cb(ev->topic, ev->topic_len,
                        ev->data,  ev->data_len);
            }
            break;

        case MQTT_EVENT_ERROR:
            ESP_LOGE(TAG, "Error.");
            break;

        default:
            break;
    }
}

void pal_mqtt_init(const char *broker_uri) {
    esp_mqtt_client_config_t cfg = {
        .broker.address.uri  = (broker_uri != NULL) ? broker_uri
                                                      : CONFIG_MOQUI_MQTT_BROKER_URI,
        .session.protocol_ver = MQTT_PROTOCOL_V_5
    };
    s_client = esp_mqtt_client_init(&cfg);
    esp_mqtt_client_register_event(s_client, ESP_EVENT_ANY_ID, mqtt_event_handler, NULL);
    esp_mqtt_client_start(s_client);
}

bool pal_mqtt_is_connected(void) {
    return s_connected;
}

int pal_mqtt_publish(const char *topic, const char *payload, int len, int qos) {
    if (!s_connected || s_client == NULL) { return -1; }
    return esp_mqtt_client_publish(s_client, topic, payload, len, qos, 0);
}

int pal_mqtt_subscribe(const char *topic, int qos) {
    if (!s_connected || s_client == NULL) { return -1; }
    return esp_mqtt_client_subscribe(s_client, topic, qos);
}

void pal_mqtt_set_rx_cb(PalMqttRxCb cb) {
    s_rx_cb = cb;
}

#ifndef HOST_MQTT_CLIENT_H
#define HOST_MQTT_CLIENT_H
#include <stdint.h>
#include <stdbool.h>
typedef void *esp_mqtt_client_handle_t;
typedef const char *esp_event_base_t;
typedef enum {MQTT_EVENT_CONNECTED=1,MQTT_EVENT_DISCONNECTED,MQTT_EVENT_DATA,MQTT_EVENT_ERROR} esp_mqtt_event_id_t;
typedef struct { char *topic; int topic_len; char *data; int data_len; int total_data_len; int current_data_offset; } esp_mqtt_event_t;
typedef esp_mqtt_event_t *esp_mqtt_event_handle_t;
typedef struct { struct { struct { const char *uri; } address; } broker; struct { int protocol_ver; } session; } esp_mqtt_client_config_t;
#define MQTT_PROTOCOL_V_5 5
#define ESP_EVENT_ANY_ID -1
esp_mqtt_client_handle_t esp_mqtt_client_init(const esp_mqtt_client_config_t *config);
int esp_mqtt_client_register_event(esp_mqtt_client_handle_t client, int event, void (*callback)(void *,esp_event_base_t,int32_t,void *), void *arg);
int esp_mqtt_client_start(esp_mqtt_client_handle_t client);
int esp_mqtt_client_enqueue(esp_mqtt_client_handle_t client,const char *topic,const char *data,int len,int qos,int retain,bool store);
int esp_mqtt_client_subscribe(esp_mqtt_client_handle_t client,const char *topic,int qos);
int esp_mqtt_client_unsubscribe(esp_mqtt_client_handle_t client,const char *topic);
#endif

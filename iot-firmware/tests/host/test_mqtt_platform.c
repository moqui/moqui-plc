#include "mqtt_client.h"
#include "platform.h"
#include <assert.h>
#include <string.h>
#include <stdio.h>
static void (*handler)(void *,esp_event_base_t,int32_t,void *);
static unsigned received, enqueued;
esp_mqtt_client_handle_t esp_mqtt_client_init(const esp_mqtt_client_config_t *c) { assert(c->session.protocol_ver==5); return &received; }
int esp_mqtt_client_register_event(esp_mqtt_client_handle_t c,int e,void (*cb)(void *,esp_event_base_t,int32_t,void *),void *a) {
    (void)c;(void)e;(void)a;handler=cb;return 0;
}
int esp_mqtt_client_start(esp_mqtt_client_handle_t c) { (void)c;return 0; }
int esp_mqtt_client_enqueue(esp_mqtt_client_handle_t c,const char *t,const char *d,int len,int q,int r,bool store) {
    (void)c;(void)t;(void)d;(void)len;(void)q;(void)r;assert(store);++enqueued;return 1;
}
int esp_mqtt_client_subscribe(esp_mqtt_client_handle_t c,const char *t,int q) { (void)c;(void)t;(void)q;return 1; }
int esp_mqtt_client_unsubscribe(esp_mqtt_client_handle_t c,const char *t) { (void)c;(void)t;return 1; }
static void rx(const char *topic,int tlen,const char *data,int len) {
    assert(tlen==4 && memcmp(topic,"test",4)==0);
    assert(len==7 && memcmp(data,"{\"x\":1}",7)==0); ++received;
}
int main(void) {
    pal_mqtt_init(NULL);pal_mqtt_set_rx_cb(rx);
    assert(!pal_mqtt_is_connected());
    handler(NULL,NULL,MQTT_EVENT_CONNECTED,NULL);assert(pal_mqtt_is_connected());
    esp_mqtt_event_t a={.topic="test",.topic_len=4,.data="{\"x",.data_len=3,.total_data_len=7};
    handler(NULL,NULL,MQTT_EVENT_DATA,&a);assert(received==0);
    esp_mqtt_event_t b={.data="\":1}",.data_len=4,.total_data_len=7,.current_data_offset=3};
    handler(NULL,NULL,MQTT_EVENT_DATA,&b);assert(received==1);
    b.current_data_offset=2;handler(NULL,NULL,MQTT_EVENT_DATA,&a);handler(NULL,NULL,MQTT_EVENT_DATA,&b);assert(received==1);
    a.total_data_len=4096;handler(NULL,NULL,MQTT_EVENT_DATA,&a);assert(received==1);
    assert(pal_mqtt_publish("test","{}",2,0)==1 && enqueued==1);
    handler(NULL,NULL,MQTT_EVENT_DISCONNECTED,NULL);assert(!pal_mqtt_is_connected());
    assert(pal_mqtt_publish("test","{}",2,0)==-1);
    puts("MQTT PAL fragment and transport regressions passed");return 0;
}

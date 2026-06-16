#include "MqttParameterSub.h"
#include "platform.h"
#include <stdio.h>
#include <string.h>

/* MISRA C:2012 Rule 15.5 deviation: early returns used for guard clauses. */

/* Singleton reference — the PAL rx callback dispatches to the active subscriber. */
static MqttParameterSub *s_active_sub = NULL;

static void rx_callback(const char *topic, int topic_len,
                        const char *payload, int payload_len) {
    int sub_topic_len;
    (void)topic;
    (void)topic_len;

    if (!s_active_sub || !s_active_sub->parseFn || !s_active_sub->device) { return; }

    sub_topic_len = (int)strlen(MOQUI_LIVE_PARAMS_SUB_TOPIC);
    /* Only dispatch if this message arrives on our subscribe topic. */
    if (topic_len >= sub_topic_len &&
        strncmp(topic + (topic_len - sub_topic_len),
                MOQUI_LIVE_PARAMS_SUB_TOPIC,
                (size_t)sub_topic_len) == 0) {
        s_active_sub->parseFn(payload, payload_len, s_active_sub->device);
    }
}

void MqttParameterSub_Update(MqttParameterSub *sub, bool paramsSubEnable) {
    if (!sub->init) {
        pal_mqtt_set_rx_cb(rx_callback);
        sub->init = true;
    }

    if (!paramsSubEnable) {
        sub->done       = false;
        sub->busy       = false;
        sub->error      = false;
        sub->errorId    = 0;
        sub->subscribed = false;
        s_active_sub    = NULL;
        return;
    }

    if (!sub->subscribed) {
        sub->busy = true;
        int mid = pal_mqtt_subscribe(MOQUI_LIVE_PARAMS_SUB_TOPIC, 0);
        if (mid >= 0) {
            printf("[D][MqttParameterSub] Subscribed to %s, mid=%d\n", MOQUI_LIVE_PARAMS_SUB_TOPIC, mid);
            sub->subscribed = true;
            sub->done       = true;
            sub->error      = false;
            s_active_sub    = sub;
        } else {
            printf("[W][MqttParameterSub] Subscribe failed, will retry next cycle.\n");
            sub->error   = true;
            sub->errorId = 1;
        }
        sub->busy = false;
    }
}

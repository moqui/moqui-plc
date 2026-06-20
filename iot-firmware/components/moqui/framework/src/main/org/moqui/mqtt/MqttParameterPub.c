#include "MqttParameterPub.h"
#include "MqttClient.h"
#include <stdio.h>

/* MISRA C:2012 Rule 15.5 deviation: early returns used for guard clauses. */

void MqttParameterPub_Update(MqttParameterPub *pub, bool paramsPubEnable) {
    char json_buf[JSON_PAYLOAD_MAX_SIZE];

    if (!pub->init) { pub->init = true; }

    if (!paramsPubEnable) {
        pub->done    = false;
        pub->busy    = false;
        pub->error   = false;
        pub->errorId = 0;
        return;
    }

    if (!pub->serializeFn || !pub->device) { return; }

    if (!pub->busy) {
        pub->busy = true;

        if (pub->serializeFn(pub->device, json_buf, sizeof(json_buf))) {
            MqttClient_PublishDeviceStatus(json_buf);
            printf("[D][MqttParameterPub] Parameters enqueued for publish.\n");
            pub->done  = true;
            pub->error = false;
        } else {
            printf("[E][MqttParameterPub] Failed to serialize device parameters.\n");
            pub->done    = false;
            pub->error   = true;
            pub->errorId = 1;
        }

        pub->busy = false;
    }
}

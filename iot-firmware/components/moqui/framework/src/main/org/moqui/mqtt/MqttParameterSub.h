#ifndef MQTT_PARAMETER_SUB_H
#define MQTT_PARAMETER_SUB_H

/*
 * MqttParameterSub — port of MqttParameterSub.st (FUNCTION_BLOCK).
 *
 * Subscribes to the liveParamsSubTopic on first enable and routes incoming
 * JSON payloads to the injected parse_fn callback (JsonToParametersMapper_ParseAndApply).
 */

#include <stdint.h>
#include <stdbool.h>
#include "MoquiConf.h"

/* Callback invoked for each received MQTT message.
 * payload is NOT null-terminated; use payload_len. */
typedef void (*ParamParseFn)(const char *payload, int payload_len, void *device);

typedef struct {
    /* VAR_INPUT (injected at init) */
    void       *device;    /* DeviceFacade * cast to void * */
    ParamParseFn parseFn;  /* e.g. adapter calling JsonToParametersMapper_ParseAndApply */

    /* VAR_OUTPUT */
    bool    done;
    bool    busy;
    bool    error;
    int16_t errorId;

    /* VAR */
    bool init;
    bool subscribed;
} MqttParameterSub;

void MqttParameterSub_Update(MqttParameterSub *sub, bool paramsSubEnable);

#endif /* MQTT_PARAMETER_SUB_H */

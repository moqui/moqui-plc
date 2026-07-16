#ifndef MQTT_PARAMETER_PUB_H
#define MQTT_PARAMETER_PUB_H

/*
 * MqttParameterPub — optional peer-PLC parameter replication, typically for a
 * developer-defined redundancy strategy. Telemetry belongs to LogDispatcher.
 *
 * Dependency inversion: the serialization function and the device pointer are
 * injected via callback so that this framework-layer header has no dependency
 * on runtime-layer types (DeviceFacade, ParametersToJsonMapper).
 * Wire serialize_fn = serialize_device_facade in main.c.
 */

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include "MoquiConf.h"

/* Serializer callback type — matches serialize_device_facade() signature. */
typedef bool (*ParamSerializeFn)(const void *device, char *buf, size_t max_len);

typedef struct {
    /* VAR_INPUT (injected at init, immutable during operation) */
    const void      *device;       /* DeviceFacade * cast to void * */
    ParamSerializeFn serializeFn;  /* e.g. (ParamSerializeFn)serialize_device_facade */

    /* VAR_OUTPUT */
    bool    done;
    bool    busy;
    bool    error;
    int16_t errorId;

    /* VAR */
    bool init;
} MqttParameterPub;

void MqttParameterPub_Update(MqttParameterPub *pub, bool paramsPubEnable);

#endif /* MQTT_PARAMETER_PUB_H */

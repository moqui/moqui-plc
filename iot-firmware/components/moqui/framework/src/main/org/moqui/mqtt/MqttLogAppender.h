#ifndef MQTT_LOG_APPENDER_H
#define MQTT_LOG_APPENDER_H

#include <stdint.h>
#include <stdbool.h>
#include "LogEvent.h"

typedef struct {
    /* VAR_INPUT */
    bool execute;
    LogEvent *logBuffer;
    uint16_t logBufferSize;

    /* VAR_OUTPUT */
    bool done;
    bool busy;
    bool error;
    int16_t errorId;

    /* VAR */
    bool init;

} MqttLogAppender;

void MqttLogAppender_Update(MqttLogAppender *appender);

#endif /* MQTT_LOG_APPENDER_H */

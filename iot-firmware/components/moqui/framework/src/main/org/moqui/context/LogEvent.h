#ifndef LOG_EVENT_H
#define LOG_EVENT_H

#include <stdint.h>
#include "LogMarker.h"
#include "LogLevel.h"
#include "LogPayloadType.h"
#include "LogPayload.h"

typedef struct {
    char logEventId[32];
    char loggerName[64];
    LogMarker marker;
    LogLevel level;
    uint64_t logEventDate; /* Using timestamp representation */
    char source[64];
    LogPayloadType payloadType;
    LogPayload payload;
    /* 1 for an event; N for the summary of N repetitions ("last message repeated N times"). */
    uint16_t repeatCount;
    /* Position of the record in the logger ring, set when stored: consecutive records differ by 1. */
    uint32_t sequence;
} LogEvent;

#endif /* LOG_EVENT_H */

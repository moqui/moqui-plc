#ifndef LOG_SOURCE_H
#define LOG_SOURCE_H

#include <stdint.h>
#include "LoggerFacade.h"
#include "MoquiConf.h"

/* LOG_SOURCE_LIST_MAX_SIZE defined in MoquiConf.h */

/*
 * Port of LogSource.st, kept for interface compatibility. On IoT targets every
 * LoggerFacade writes the single ring of LoggerFacade.c from the control task,
 * and MqttLogAppender is its only consumer (see LoggerFacade_PeekBuffer).
 */
typedef struct {
    LoggerFacade *logRef;
    uint16_t readSlot;
    uint32_t reportedDropCount;
    uint32_t publishedCount;
    uint32_t discardedCount;
} LogSource;

#endif /* LOG_SOURCE_H */

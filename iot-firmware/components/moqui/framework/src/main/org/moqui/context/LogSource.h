#ifndef LOG_SOURCE_H
#define LOG_SOURCE_H

#include <stdint.h>
#include "LoggerFacade.h"
#include "MoquiConf.h"

/* LOG_SOURCE_LIST_MAX_SIZE defined in MoquiConf.h */

/* Since LogRingBuffer was replaced by native ESP_LOG in Phase 8, */
/* this struct is kept for interface compatibility. */
typedef struct {
    LoggerFacade *logRef;
    uint16_t lastLogSize;
    uint16_t lastHead;
    uint16_t lastTail;
    uint32_t lastOverflowCount;
} LogSource;

#endif /* LOG_SOURCE_H */

#ifndef EC_H
#define EC_H

#include <stdbool.h>
#include <stdint.h>
#include "Clocks.h"
#include "LogSource.h"
#include "DeviceFacade.h"

/* Forward declaration to avoid full include tree if not necessary */
typedef struct IOFacade IOFacade;
typedef struct WorkEffort WorkEffort;

/* Execution Context (ec.st) equivalent */
typedef struct {
    Clocks clks;
    
    /* Framework args */
    bool enable;
    bool init;
    bool fault;
    bool error;
    bool commError;
    bool reset;
    bool autoReset;
    bool allConfigLoaded;
    
    uint16_t retryCount;
    uint16_t retryTime;
    
    bool isPrimary;
    uint64_t heartbeat;

    /* Logger */
    LogSource logSourceList[LOG_SOURCE_LIST_MAX_SIZE];
    uint16_t logSourceListSize;

    /* Facades */
    DeviceFacade *dev;
    IOFacade *io;
    
    /* Optional */
    WorkEffort *workEffort;

    /* MQTT pub/sub */
    bool logAppenderEnable;
    bool paramsPubEnable;
    bool paramsSubEnable;
} ExecutionContext;

/* Global instance (matching VAR_GLOBAL in ec.st) */
extern ExecutionContext ec;

#endif /* EC_H */

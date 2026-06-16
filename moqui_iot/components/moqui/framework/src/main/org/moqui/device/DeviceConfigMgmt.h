#ifndef DEVICE_CONFIG_MGMT_H
#define DEVICE_CONFIG_MGMT_H

#include <stdint.h>
#include <stdbool.h>
#include "DeviceConfigMgmtStatus.h"
#include "DeviceConfigCmds.h"
#include "LoggerFacade.h"

/*
 * Sequential device-config load sequencer.
 * Faithful port of DeviceConfigMgmt.st (FUNCTION_BLOCK DeviceConfigMgmt).
 *
 * Walks configCmds.configNameList in order, emitting one configName at a time
 * and waiting for configCompleted feedback before moving to the next entry.
 * Uses an R_TRIG pattern on configCompleted (rising edge only).
 */

typedef struct {
    /* VAR_INPUT */
    bool enable;
    bool continueAfterError;
    bool configCompleted; /* Rising-edge acknowledgment from the consumer */

    /* VAR_OUTPUT */
    bool     done;
    bool     allConfigLoaded;
    bool     busy;
    bool     error;
    uint32_t errorId;

    /* VAR */
    DeviceConfigMgmtStatus status;
    DeviceConfigCmds    configCmds;
    uint16_t               currentConfigIndex;
    bool                   init;
    bool                   configCompletedPrev; /* R_TRIG: previous cycle value */

    LoggerFacade logger;

} DeviceConfigMgmt;

void DeviceConfigMgmt_Update(DeviceConfigMgmt *self);

#endif /* DEVICE_CONFIG_MGMT_H */

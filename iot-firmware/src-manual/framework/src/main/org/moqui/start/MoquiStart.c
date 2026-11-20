#include "MoquiStart.h"
#include "MoquiConf.h"
#include <stddef.h>

/* MISRA C:2012 Rule 15.5 deviation: early returns used for guard clauses throughout. */

void MoquiStart_Update(MoquiStart *start, Clocks *clks) {
    if (start->init) {
        start->logger.enable = true;
        start->logger.loggerName = MOQUI_APPLICATION_DEVICE_ID;
        start->operationType = OPERATING_MODE_INIT;
        start->mainInitPending = true;
    } else {
        start->operationType = OPERATING_MODE_RUN;
    }

    start->clockGen.operationType = start->operationType;
    ClockGeneration_Update(&start->clockGen, clks);

    /* I/O signal scan — reads hardware inputs and writes outputs each cycle */
    start->inputProcessing.operationType = start->operationType;
    InputSignalUpdate_Update(&start->inputProcessing);

    /* Config loading sequencer */
    start->configMgmt.enable = start->enable;
    start->configMgmt.configCompleted = start->mainDone; /* Rising-edge ack from Main */
    start->configMgmt.reset = start->configResetRequest;
    DeviceConfigMgmt_Update(&start->configMgmt);
    start->configResetRequest = false;
    start->allConfigLoaded = start->configMgmt.allConfigLoaded;
    start->configError = start->configMgmt.error;

    /* Rising edge on mainDone triggers device-config context reset */
    if (start->mainDone && !start->mainDoneOld) {
        start->deviceConfigContextResetRequest = true;
    }
    start->mainDoneOld = start->mainDone;

    switch (start->status) {
        case MOQUI_START_STATUS_IDLE:
            if (!start->error && start->enable) {
                LOGGER_LOG(&start->logger, LOG_LEVEL_INFO, "Framework started.");
                start->mainDone = false;
                start->deviceConfigContextResetRequest = false;
                start->status = MOQUI_START_STATUS_RUN;
            }
            break;

        case MOQUI_START_STATUS_RUN:
            if (start->configMgmt.error) {
                start->status = MOQUI_START_STATUS_ERROR;
            } else if (!start->configMgmt.busy) {
                if (start->configMgmt.allConfigLoaded) {
                    LOGGER_LOG(&start->logger, LOG_LEVEL_INFO, "All device configs loaded. Framework idle.");
                    start->retryCount = 0U; /* A completed run ends the retry sequence */
                    start->enable = false;
                    start->status = MOQUI_START_STATUS_IDLE;
                } else {
                    if (start->mainUpdate == NULL) {
                        start->mainError = true;
                        start->status = MOQUI_START_STATUS_ERROR;
                    } else {
                        start->mainUpdate(start->mainContext, clks,
                            start->mainInitPending ? OPERATING_MODE_INIT : OPERATING_MODE_RUN,
                            start->enable, start->deviceConfigContextResetRequest,
                            &start->mainDone, &start->mainError);
                        start->mainInitPending = false;
                        if (start->mainError) { start->status = MOQUI_START_STATUS_ERROR; }
                    }
                    start->deviceConfigContextResetRequest = false;
                }
            }
            break;

        case MOQUI_START_STATUS_ERROR:
            start->retryReset = false;
            if (MOQUI_RETRY_ON_ERROR && start->retryCount < MOQUI_MAX_RETRY_COUNT) {
                if (clks->clock1s) {
                    start->retryTime++;
                }
                if (start->retryTime >= MOQUI_MIN_RETRY_TIME) {
                    LOGGER_LOG(&start->logger, LOG_LEVEL_WARN, "Retrying after error ...");
                    start->retryCount++;
                    start->retryTime = 0;
                    start->retryReset = true;
                }
            }

            if (start->reset || start->autoReset || start->retryReset) {
                LOGGER_LOG(&start->logger, LOG_LEVEL_WARN, "Resetting framework after error.");
                /* Only a reset from the supervision restarts the retry count: MOQUI_MAX_RETRY_COUNT bounds the automatic ones */
                if (start->reset || start->autoReset) { start->retryCount = 0; }
                start->retryReset = false;
                start->retryTime = 0;
                start->mainError = false;
                start->configResetRequest = true;
                start->mainInitPending = true;
                start->deviceConfigContextResetRequest = false;
                start->status = MOQUI_START_STATUS_IDLE;
            }
            break;

        default:
            break;
    }

    /* Single writer of error: the latched Error state, or a device config error still present */
    start->error = (start->status == MOQUI_START_STATUS_ERROR) || start->configError;

    start->outputProcessing.operationType = start->operationType;
    OutputSignalUpdate_Update(&start->outputProcessing);
    start->init = false;
}

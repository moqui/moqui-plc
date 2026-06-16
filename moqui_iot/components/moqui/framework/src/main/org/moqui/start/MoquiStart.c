#include "MoquiStart.h"
#include "MoquiConf.h"

/* MISRA C:2012 Rule 15.5 deviation: early returns used for guard clauses throughout. */

void MoquiStart_Update(MoquiStart *start, Clocks *clks) {
    if (start->init) {
        start->logger.enable = true;
        start->logger.loggerName = "moqui";
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
    start->outputProcessing.operationType = start->operationType;
    OutputSignalUpdate_Update(&start->outputProcessing);

    /* Config loading sequencer */
    start->configMgmt.enable = start->enable;
    start->configMgmt.configCompleted = start->mainDone; /* Rising-edge ack from Main */
    DeviceConfigMgmt_Update(&start->configMgmt);
    start->allConfigLoaded = start->configMgmt.allConfigLoaded;
    if (start->configMgmt.error) {
        start->error = true;
    }

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
                    start->enable = false;
                    start->status = MOQUI_START_STATUS_IDLE;
                } else {
                    /* Call main(operationType, enable...) */
                    start->mainInitPending = false;
                    start->deviceConfigContextResetRequest = false;
                }
            }
            break;

        case MOQUI_START_STATUS_ERROR:
            if (MOQUI_RETRY_ON_ERROR && start->retryCount < MOQUI_MAX_RETRY_COUNT) {
                if (clks->clock1s) {
                    start->retryTime++;
                }
                if (start->retryTime >= MOQUI_MIN_RETRY_TIME) {
                    LOGGER_LOG(&start->logger, LOG_LEVEL_WARN, "Retrying after error ...");
                    start->retryCount++;
                    start->retryTime = 0;
                    start->autoReset = true;
                }
            }

            if (start->reset || start->autoReset) {
                LOGGER_LOG(&start->logger, LOG_LEVEL_WARN, "Resetting framework after error.");
                start->error = false;
                start->retryCount = 0;
                start->retryTime = 0;
                start->mainInitPending = true;
                start->deviceConfigContextResetRequest = false;
                start->status = MOQUI_START_STATUS_IDLE;
                start->autoReset = false;
            }
            break;

        default:
            break;
    }

    start->init = false;
}

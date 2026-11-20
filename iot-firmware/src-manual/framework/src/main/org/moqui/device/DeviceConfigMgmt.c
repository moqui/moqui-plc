#include "DeviceConfigMgmt.h"
#include <string.h>

void DeviceConfigMgmt_Update(DeviceConfigMgmt *self)
{
    bool configCompletedEdge;
    bool resetEdge;

    if (!self->init) {
        LoggerFacade_Init(&self->logger, MOQUI_APPLICATION_DEVICE_ID);
        self->init   = true;
        self->status = DEVICE_CONFIG_MGMT_IDLE;
    }

    /* R_TRIG on configCompleted */
    configCompletedEdge = (self->configCompleted && !self->configCompletedPrev);
    self->configCompletedPrev = self->configCompleted;
    /* R_TRIG on reset */
    resetEdge = (self->reset && !self->resetPrev);
    self->resetPrev = self->reset;

    switch (self->status) {
        case DEVICE_CONFIG_MGMT_IDLE:
            self->done = false;
            self->busy = false;

            if (self->enable) {
                self->busy = true;
                self->configCmds.configType = self->configCmds.defaultConfigType;
                self->status = DEVICE_CONFIG_MGMT_INIT;
            }
            break;

        case DEVICE_CONFIG_MGMT_INIT:
            self->allConfigLoaded = false;
            self->configCmds.cmd  = DEVICE_CONFIG_CMD_INIT;
            DeviceConfigCmds_Update(&self->configCmds);
            self->error   = self->configCmds.error;
            self->errorId = self->configCmds.errorId;

            if (self->configCmds.error) {
                self->status = DEVICE_CONFIG_MGMT_RESETTING;
            } else {
                self->status = DEVICE_CONFIG_MGMT_LOAD;
            }
            break;

        case DEVICE_CONFIG_MGMT_LOAD:
            if (self->currentConfigIndex >= self->configCmds.configNameListSize) {
                self->busy   = true;
                self->status = DEVICE_CONFIG_MGMT_COMPLETED;
            } else {
                self->configCmds.configName =
                    self->configCmds.configNameList[self->currentConfigIndex];
                self->configCmds.cmd = DEVICE_CONFIG_CMD_LOAD;
                DeviceConfigCmds_Update(&self->configCmds);
                self->error   = self->configCmds.error;
                self->errorId = self->configCmds.errorId;

                if (self->configCmds.error) {
                    self->status = DEVICE_CONFIG_MGMT_RESETTING;
                } else {
                    self->status = DEVICE_CONFIG_MGMT_WAIT_PROCESSING;
                }
            }
            break;

        case DEVICE_CONFIG_MGMT_WAIT_PROCESSING:
            self->done = true;
            self->busy = false;

            if (configCompletedEdge) {
                self->done = false;
                LOGGER_LOG(&self->logger, LOG_LEVEL_INFO, "Device config %s completed.", self->configCmds.configName);
                self->currentConfigIndex++;
                self->status = DEVICE_CONFIG_MGMT_LOAD;
            }
            break;

        case DEVICE_CONFIG_MGMT_COMPLETED:
            self->allConfigLoaded = true;
            self->done            = true;
            self->busy            = false;
            self->error           = false;
            self->currentConfigIndex = 0U;
            LOGGER_LOG(&self->logger, LOG_LEVEL_INFO, "All device configs loaded.");
            self->status = DEVICE_CONFIG_MGMT_IDLE;
            break;

        case DEVICE_CONFIG_MGMT_RESETTING:
            /* error and errorId keep the failed command's values */
            self->configCmds.cmd = DEVICE_CONFIG_CMD_RESET;
            DeviceConfigCmds_Update(&self->configCmds);

            if (!self->continueAfterError) {
                self->currentConfigIndex = 0U;
            }
            LOGGER_LOG(&self->logger, LOG_LEVEL_ERROR, "Device config error. Waiting for a reset.");
            self->status = DEVICE_CONFIG_MGMT_ERROR;
            break;

        /*
         * A failed command (Init/Load) resets the recipe manager once and stops here, with error kept true:
         * a rising edge of reset starts again. It does not reload the recipes in a loop.
         */
        case DEVICE_CONFIG_MGMT_ERROR:
            self->error = true;
            self->busy  = false;
            self->done  = false;
            if (resetEdge) {
                self->error   = false;
                self->errorId = 0U;
                self->status  = DEVICE_CONFIG_MGMT_IDLE;
            }
            break;

        default:
            break;
    }
}

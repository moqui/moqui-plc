#include "DeviceConfigMgmt.h"
#include <string.h>

void DeviceConfigMgmt_Update(DeviceConfigMgmt *self)
{
    bool configCompletedEdge;

    if (!self->init) {
        LoggerFacade_Init(&self->logger, "DeviceConfigMgmt");
        self->init   = true;
        self->status = DEVICE_CONFIG_MGMT_IDLE;
    }

    /* R_TRIG on configCompleted */
    configCompletedEdge = (self->configCompleted && !self->configCompletedPrev);
    self->configCompletedPrev = self->configCompleted;

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
                self->currentConfigIndex = 0U;
                self->status = DEVICE_CONFIG_MGMT_LOAD;
            }
            break;

        case DEVICE_CONFIG_MGMT_LOAD:
            if (self->currentConfigIndex >= self->configCmds.configNameListSize) {
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
                LOGGER_LOG(&self->logger, LOG_LEVEL_INFO, "Device config completed.");
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
            self->configCmds.cmd = DEVICE_CONFIG_CMD_RESET;
            DeviceConfigCmds_Update(&self->configCmds);
            self->error   = self->configCmds.error;
            self->errorId = self->configCmds.errorId;

            if (!self->continueAfterError) {
                self->currentConfigIndex = 0U;
            }
            self->status = DEVICE_CONFIG_MGMT_INIT;
            break;

        default:
            break;
    }
}

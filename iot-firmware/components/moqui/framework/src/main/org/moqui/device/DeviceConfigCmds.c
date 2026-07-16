#include "DeviceConfigCmds.h"
#include <string.h>

/* MISRA C:2012 Rule 15.5 deviation: early returns used for guard clauses throughout. */

/* -------------------------------------------------------------------------
 * Bubble-sort configNameList alphabetically ascending (mirrors ST REPEAT loop)
 * ---------------------------------------------------------------------- */
static void sort_name_list(DeviceConfigCmds *self)
{
    bool     swapped;
    uint16_t j;
    char     tmp[64];

    if (self->configNameListSize <= 1U) {
        return;
    }

    do {
        swapped = false;
        for (j = 0U; j < (self->configNameListSize - 1U); j++) {
            if (strcmp(self->configNameList[j], self->configNameList[j + 1U]) > 0) {
                memcpy(tmp,                          self->configNameList[j],       sizeof(tmp));
                memcpy(self->configNameList[j],      self->configNameList[j + 1U], sizeof(tmp));
                memcpy(self->configNameList[j + 1U], tmp,                           sizeof(tmp));
                swapped = true;
            }
        }
    } while (swapped);
}

/* -------------------------------------------------------------------------
 * DeviceConfigCmds_Update
 * ---------------------------------------------------------------------- */
void DeviceConfigCmds_Update(DeviceConfigCmds *self)
{
    const char *type;
    const char *name;
    uint16_t    i;

    /* One-time logger init (mirrors ST Init branch) */
    if (!self->loggerInit) {
        LoggerFacade_Init(&self->logger, MOQUI_APPLICATION_DEVICE_ID);
        self->loggerInit = true;
    }

    self->error   = false;
    self->errorId = 0U;

    /* Resolve effective configType */
    type = ((self->configType != NULL) && (self->configType[0] != '\0'))
           ? self->configType
           : self->defaultConfigType;

    name = self->configName;

    /* Validate arguments */
    if ((type == NULL) || (type[0] == '\0') ||
        ((self->cmd != DEVICE_CONFIG_CMD_INIT) &&
         (self->cmd != DEVICE_CONFIG_CMD_RESET) &&
         ((name == NULL) || (name[0] == '\0')))) {
        LOGGER_LOG(&self->logger, LOG_LEVEL_ERROR, "Invalid arguments.");
        self->error   = true;
        self->errorId = 0x5000U;
        return;
    }

    if ((self->configOps == NULL)) {
        LOGGER_LOG(&self->logger, LOG_LEVEL_ERROR, "No configOps provided.");
        self->error   = true;
        self->errorId = 0x5001U;
        return;
    }

    switch (self->cmd) {
        case DEVICE_CONFIG_CMD_INIT:
            LOGGER_LOG(&self->logger, LOG_LEVEL_INFO, "Loading device config list.");
            for (i = 0U; i <= DEVICE_CONFIG_LIST_MAX_SIZE; i++) {
                self->configNameList[i][0] = '\0';
            }
            self->configNameListSize = 0U;

            if (!self->configOps->listConfigs) {
                LOGGER_LOG(&self->logger, LOG_LEVEL_WARN, "listConfigs not implemented.");
                break;
            }
            self->errorId = self->configOps->listConfigs(self->configOps->context,
                self->deviceConfigStoragePath, type,
                self->configNameList, DEVICE_CONFIG_LIST_MAX_SIZE + 1U,
                &self->configNameListSize);

            self->error = (self->errorId != 0U);
            if (self->error) {
                LOGGER_LOG(&self->logger, LOG_LEVEL_ERROR, "Error loading device config list from filesystem.");
                return;
            }

            sort_name_list(self);
            break;

        case DEVICE_CONFIG_CMD_CREATE:
            if (!self->configOps->createConfig) {
                LOGGER_LOG(&self->logger, LOG_LEVEL_WARN, "createConfig not implemented.");
                break;
            }
            self->errorId = self->configOps->createConfig(self->configOps->context,
                self->deviceConfigStoragePath, type, name);
            self->error = (self->errorId != 0U);
            if (self->error) {
                LOGGER_LOG(&self->logger, LOG_LEVEL_ERROR, "Error creating device config.");
            } else {
                LOGGER_LOG(&self->logger, LOG_LEVEL_INFO, "Created device config.");
            }
            break;

        case DEVICE_CONFIG_CMD_SAVE:
            if (!self->configOps->saveConfig) {
                LOGGER_LOG(&self->logger, LOG_LEVEL_WARN, "saveConfig not implemented.");
                break;
            }
            self->errorId = self->configOps->saveConfig(self->configOps->context,
                self->deviceConfigStoragePath, type, name);
            self->error = (self->errorId != 0U);
            if (self->error) {
                LOGGER_LOG(&self->logger, LOG_LEVEL_ERROR, "Error saving device config.");
            } else {
                LOGGER_LOG(&self->logger, LOG_LEVEL_INFO, "Saved device config.");
            }
            break;

        case DEVICE_CONFIG_CMD_LOAD:
            if (!self->configOps->loadConfig) {
                LOGGER_LOG(&self->logger, LOG_LEVEL_WARN, "loadConfig not implemented.");
                break;
            }
            self->errorId = self->configOps->loadConfig(self->configOps->context,
                self->deviceConfigStoragePath, type, name);
            self->error = (self->errorId != 0U);
            if (self->error) {
                LOGGER_LOG(&self->logger, LOG_LEVEL_ERROR, "Error loading device config.");
            } else {
                LOGGER_LOG(&self->logger, LOG_LEVEL_INFO, "Loaded device config.");
            }
            break;

        case DEVICE_CONFIG_CMD_DELETE:
            if (!self->configOps->deleteConfig) {
                LOGGER_LOG(&self->logger, LOG_LEVEL_WARN, "deleteConfig not implemented.");
                break;
            }
            self->errorId = self->configOps->deleteConfig(self->configOps->context,
                self->deviceConfigStoragePath, type, name);
            self->error = (self->errorId != 0U);
            if (self->error) {
                LOGGER_LOG(&self->logger, LOG_LEVEL_ERROR, "Error deleting device config.");
            } else {
                LOGGER_LOG(&self->logger, LOG_LEVEL_INFO, "Deleted device config.");
            }
            break;

        case DEVICE_CONFIG_CMD_RESET:
            LOGGER_LOG(&self->logger, LOG_LEVEL_INFO, "Resetting device config list.");
            self->error   = false;
            self->errorId = 0U;
            break;

        default:
            break;
    }
}

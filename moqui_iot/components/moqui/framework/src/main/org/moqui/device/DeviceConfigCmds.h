#ifndef DEVICE_CONFIG_CMDS_H
#define DEVICE_CONFIG_CMDS_H

#include <stdint.h>
#include <stdbool.h>
#include "DeviceConfigCmdType.h"
#include "LoggerFacade.h"
#include "MoquiConf.h"

/*
 * Device configuration file management commands.
 * Faithful port of DeviceConfigCmds.st (FUNCTION_BLOCK DeviceConfigCmds).
 *
 * The ST version uses CODESYS Recipe_Management.RecipeManCommands internally.
 * This IoT port abstracts file I/O through platform callbacks (configOps),
 * so the logic layer remains platform-neutral.
 *
 * File name convention (matches ST): <configName>.<configType>.<ext>
 */

/* DEVICE_CONFIG_LIST_MAX_SIZE defined in MoquiConf.h */

/*
 * Platform filesystem abstraction — caller provides an implementation.
 * All functions return 0 on success, non-zero error code on failure.
 * context is passed as first argument to every ops function.
 */
typedef struct {
    void *context;  /* Passed as first argument to all ops functions */

    /* List config names of the given type stored on the filesystem.
     * names: caller-provided array of (DEVICE_CONFIG_LIST_MAX_SIZE+1) char* slots.
     * Returns count of names found via outCount. */
    uint32_t (*listConfigs)(void *ctx, const char *storagePath, const char *configType,
                            char names[][64], uint16_t maxNames, uint16_t *outCount);

    /* Create an empty config record for configName.configType */
    uint32_t (*createConfig)(void *ctx, const char *storagePath, const char *configType, const char *configName);

    /* Read current live parameters and persist to file */
    uint32_t (*saveConfig)  (void *ctx, const char *storagePath, const char *configType, const char *configName);

    /* Load parameters from file and apply to live system */
    uint32_t (*loadConfig)  (void *ctx, const char *storagePath, const char *configType, const char *configName);

    /* Delete both the file and the in-memory record */
    uint32_t (*deleteConfig)(void *ctx, const char *storagePath, const char *configType, const char *configName);

} DeviceConfigOps;

typedef struct {
    /* VAR_INPUT */
    const char          *configType;    /* If NULL/empty, uses defaultConfigType */
    const char          *configName;    /* Required for Create/Save/Load/Delete */
    DeviceConfigCmdType  cmd;

    /* VAR_EXTERNAL (injected at init) */
    const char         *defaultConfigType;
    const char         *deviceConfigStoragePath;
    const DeviceConfigOps *configOps;

    /* VAR_OUTPUT */
    char     configNameList[DEVICE_CONFIG_LIST_MAX_SIZE + 1U][64];
    uint16_t configNameListSize;
    bool     error;
    uint32_t errorId; /* 0x5000: InvalidArgs */

    /* VAR */
    LoggerFacade logger;
    bool         loggerInit;

} DeviceConfigCmds;

void DeviceConfigCmds_Update(DeviceConfigCmds *self);

#endif /* DEVICE_CONFIG_CMDS_H */

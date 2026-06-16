#ifndef DEVICE_CONFIG_CMD_TYPE_H
#define DEVICE_CONFIG_CMD_TYPE_H

/*
 * Device configuration command types (faithful port of DeviceConfigCmdType.st).
 * After each create, save or delete a new Init is required to reload the config list.
 */
typedef enum {
    DEVICE_CONFIG_CMD_INIT   = 0, /* Init the recipe management component */
    DEVICE_CONFIG_CMD_CREATE,
    DEVICE_CONFIG_CMD_SAVE,
    DEVICE_CONFIG_CMD_LOAD,
    DEVICE_CONFIG_CMD_DELETE,
    DEVICE_CONFIG_CMD_RESET
} DeviceConfigCmdType;

#endif /* DEVICE_CONFIG_CMD_TYPE_H */

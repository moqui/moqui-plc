#ifndef HVAC_DEVICE_CONFIG_OPS_H
#define HVAC_DEVICE_CONFIG_OPS_H

#include "DeviceConfigCmds.h"
#include "DeviceFacade.h"

/*
 * Provides a DeviceConfigOps implementation that loads embedded HVAC recipe
 * files via RecipeManagerCmds -> DeviceConfigLoader.
 *
 * Call HvacDeviceConfigOps_Init before passing ops to DeviceConfigMgmt.
 */
void HvacDeviceConfigOps_Init(DeviceConfigOps *ops, DeviceFacade *dev);

#endif /* HVAC_DEVICE_CONFIG_OPS_H */

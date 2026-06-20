#ifndef DEVICE_MANAGER_H
#define DEVICE_MANAGER_H

#include "DeviceFacade.h"
#include "OperatingMode.h"
#include "MainRuleEngine.h" // For Clocks definition

void DeviceManager_Update(DeviceFacade *dev, const Clocks *clks, OperatingMode operationType);

#endif // DEVICE_MANAGER_H

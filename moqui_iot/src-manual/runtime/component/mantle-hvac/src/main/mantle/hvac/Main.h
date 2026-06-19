#ifndef MAIN_H
#define MAIN_H

#include "DeviceFacade.h"
#include "MainRuleEngine.h"
#include "DeviceManager.h"
#include "OperatingMode.h"

void Main_Update(DeviceFacade *dev, const Clocks *clks, OperatingMode operationType, bool enable, bool deviceConfigContextResetRequest, bool *done, bool *error);

#endif // MAIN_H

#ifndef MAIN_RULE_ENGINE_H
#define MAIN_RULE_ENGINE_H

#include "DeviceFacade.h"
#include "OperatingMode.h"

#include "Clocks.h"

void MainRuleEngine_Update(DeviceFacade *dev, const Clocks *clks, OperatingMode operationType, bool *error);

#endif // MAIN_RULE_ENGINE_H

#ifndef HVAC_PARAMETER_LOGGER_H
#define HVAC_PARAMETER_LOGGER_H

#include "DeviceFacade.h"
#include "Clocks.h"
#include "OperatingMode.h"

void ParameterLogger_Update(const DeviceFacade *dev, const Clocks *clks,
                            OperatingMode operationType);

#endif /* HVAC_PARAMETER_LOGGER_H */

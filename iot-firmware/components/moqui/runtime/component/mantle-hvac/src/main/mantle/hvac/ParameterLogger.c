#include "ParameterLogger.h"
#include "LoggerFacade.h"
#include <stddef.h>

static LoggerFacade s_parameter_logger = {
    .enable = true,
    .loggerName = MOQUI_APPLICATION_DEVICE_ID
};

#define LOG_NUMERIC(parameter_id, value) \
    LoggerFacade_LogNumeric(&s_parameter_logger, LOG_LEVEL_INFO, (parameter_id), (double)(value))

void ParameterLogger_Update(const DeviceFacade *dev, const Clocks *clks,
                            OperatingMode operationType)
{
    if ((dev == NULL) || (clks == NULL) ||
        (operationType != OPERATING_MODE_RUN) || !clks->clock1minute) {
        return;
    }

    LOG_NUMERIC("HvacTempSetpoint", dev->tempSetpoint);
    LOG_NUMERIC("HvacTempHysteresis", dev->tempHysteresis);
    LOG_NUMERIC("HvacTempMin", dev->tempMin);
    LOG_NUMERIC("HvacTempMax", dev->tempMax);
    LOG_NUMERIC("HvacRhSetpoint", dev->rhSetpoint);
    LOG_NUMERIC("HvacRhHysteresis", dev->rhHysteresis);
    LOG_NUMERIC("HvacRhMin", dev->rhMin);
    LOG_NUMERIC("HvacRhMax", dev->rhMax);
    LOG_NUMERIC("HvacDuctTempMin", dev->ductTempMin);
    LOG_NUMERIC("HvacDuctTempMax", dev->ductTempMax);
    LOG_NUMERIC("HvacDuctRhMax", dev->ductRhMax);
    LOG_NUMERIC("HvacSetPointTimeHigh", dev->setPointTimeHigh);
    LOG_NUMERIC("HvacSetPointTimeLow", dev->setPointTimeLow);
    LOG_NUMERIC("HvacEstimatedRuntime", dev->estimatedRuntime);
    LOG_NUMERIC("HvacMinRuntime", dev->minRuntime);
    LOG_NUMERIC("HvacEstimatedBreakDuration", dev->estimatedBreakDuration);
    LOG_NUMERIC("HvacMinBreakDuration", dev->minBreakDuration);
    LOG_NUMERIC("HvacProcessEstimatedDuration", dev->processEstimatedDuration);
    LOG_NUMERIC("HvacProcessMinDuration", dev->processMinDuration);
    LOG_NUMERIC("HvacProcessRemainingDuration", dev->processRemainingDuration);
    LOG_NUMERIC("HvacProcessActualDuration", dev->processActualDuration);
    LOG_NUMERIC("HvacActualRuntime", dev->actualRuntime);
    LOG_NUMERIC("HvacActualBreakDuration", dev->actualBreakDuration);
    LOG_NUMERIC("HvacAhuFanSpeedSetpoint", dev->ahuFanSpeedSetpoint);
    LOG_NUMERIC("HvacAirFlowRef", dev->airFlowRef);
    LOG_NUMERIC("HvacTempFeedback", dev->tempFeedback);
    LOG_NUMERIC("HvacRhFeedback", dev->rhFeedback);
    LOG_NUMERIC("HvacDuctTempFeedback", dev->ductTempFeedback);
    LOG_NUMERIC("HvacDuctRhFeedback", dev->ductRhFeedback);
}

#undef LOG_NUMERIC

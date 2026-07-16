#include "Main.h"
#include "DeviceDiagnostics.h"
#include "LoggerFacade.h"
#include "AirDistributionController.h"
#include "ParameterLogger.h"

static LoggerFacade              main_logger  = { .enable = true, .loggerName = MOQUI_APPLICATION_DEVICE_ID };
static DeviceDiagnostics         s_diags      = { .operationType = OPERATING_MODE_RUN };
static AirDistributionController s_airDistrib = {0};

void Main_Update(DeviceFacade *dev, const Clocks *clks, OperatingMode operationType, bool enable, bool deviceConfigContextResetRequest, bool *done, bool *error) {
    if (!enable) return;

    if (operationType == OPERATING_MODE_INIT) {
        LOGGER_LOG(&main_logger, LOG_LEVEL_DEBUG, "Setup and configuration of all devices.");
        dev->status = MAIN_STATUS_STANDBY;
        dev->actualRuntime = 0;
        dev->actualBreakDuration = 0;
        dev->processActualDuration = 0;
        dev->processRemainingDuration = 0;
        dev->timeBreakEnabled = false;
        dev->isCompleted = false;
        *done = false;
    } else if (deviceConfigContextResetRequest) {
        LOGGER_LOG(&main_logger, LOG_LEVEL_DEBUG, "Reset HVAC device config context.");
        dev->status = MAIN_STATUS_STANDBY;
        dev->lastStatus = MAIN_STATUS_STANDBY;
        dev->actualRuntime = 0;
        dev->actualBreakDuration = 0;
        dev->processActualDuration = 0;
        dev->processRemainingDuration = 0;
        dev->timeBreakEnabled = false;
        dev->isCompleted = false;
        *done = false;
    } else {
        /* Device diagnostics must run before rule engine so cumulativeOutputAction is current */
        s_diags.operationType = operationType;
        DeviceDiagnostics_Update(&s_diags, dev);

        LOGGER_LOG(&main_logger, LOG_LEVEL_DEBUG, "Run FSM transition-condition logic.");
        MainRuleEngine_Update(dev, clks, operationType, error);
    }

    if (operationType == OPERATING_MODE_INIT || dev->status != MAIN_STATUS_STANDBY) {
        dev->lastStatus = dev->status;
    }

    if (dev->faultRequest) {
        dev->status = MAIN_STATUS_FAULT;
    }

    LOGGER_LOG(&main_logger, LOG_LEVEL_DEBUG, "Run Main FSM.");
    switch (dev->status) {
        case MAIN_STATUS_STANDBY:
            LOGGER_LOG(&main_logger, LOG_LEVEL_DEBUG, "Standby.");
            dev->standbyRequest = false;

            dev->coldGroupEnableRequest = false;
            dev->coldGroupDisableRequest = true;
            dev->hotGroupEnableRequest = false;
            dev->hotGroupDisableRequest = true;
            dev->ahuFanEnableRequest = false;
            dev->airFlowEnableRequest = false;
            dev->airFlowDisableRequest = true;

            if (dev->ventilationRequest) dev->status = MAIN_STATUS_VENTILATION;
            else if (dev->coolingRequest) dev->status = MAIN_STATUS_COOLING;
            else if (dev->heatingRequest) dev->status = MAIN_STATUS_HEATING;
            else if (dev->dryingRequest) dev->status = MAIN_STATUS_DRYING;
            break;

        case MAIN_STATUS_VENTILATION:
            LOGGER_LOG(&main_logger, LOG_LEVEL_DEBUG, "Ventilation.");
            dev->ventilationRequest = false;

            dev->coldGroupEnableRequest = false;
            dev->coldGroupDisableRequest = true;
            dev->hotGroupEnableRequest = false;
            dev->hotGroupDisableRequest = true;
            dev->ahuFanEnableRequest = true;
            dev->airFlowEnableRequest = true;
            dev->airFlowDisableRequest = false;

            if (dev->standbyRequest) dev->status = MAIN_STATUS_STANDBY;
            else if (dev->coolingRequest) dev->status = MAIN_STATUS_COOLING;
            else if (dev->heatingRequest) dev->status = MAIN_STATUS_HEATING;
            else if (dev->dryingRequest) dev->status = MAIN_STATUS_DRYING;
            break;

        case MAIN_STATUS_COOLING:
            LOGGER_LOG(&main_logger, LOG_LEVEL_DEBUG, "Cooling.");
            dev->coolingRequest = false;

            dev->coldGroupEnableRequest = true;
            dev->coldGroupDisableRequest = false;
            dev->hotGroupEnableRequest = false;
            dev->hotGroupDisableRequest = true;
            dev->ahuFanEnableRequest = true;
            dev->airFlowEnableRequest = true;
            dev->airFlowDisableRequest = false;

            if (dev->standbyRequest) dev->status = MAIN_STATUS_STANDBY;
            else if (dev->dryingRequest) dev->status = MAIN_STATUS_DRYING;
            else if (dev->ventilationRequest) dev->status = MAIN_STATUS_VENTILATION;
            break;

        case MAIN_STATUS_HEATING:
            LOGGER_LOG(&main_logger, LOG_LEVEL_DEBUG, "Heating.");
            dev->heatingRequest = false;

            dev->coldGroupEnableRequest = false;
            dev->coldGroupDisableRequest = true;
            dev->hotGroupEnableRequest = true;
            dev->hotGroupDisableRequest = false;
            dev->ahuFanEnableRequest = true;
            dev->airFlowEnableRequest = true;
            dev->airFlowDisableRequest = false;

            if (dev->standbyRequest) dev->status = MAIN_STATUS_STANDBY;
            else if (dev->dryingRequest) dev->status = MAIN_STATUS_DRYING;
            else if (dev->ventilationRequest) dev->status = MAIN_STATUS_VENTILATION;
            break;

        case MAIN_STATUS_DRYING:
            LOGGER_LOG(&main_logger, LOG_LEVEL_DEBUG, "Drying.");
            dev->dryingRequest = false;

            dev->coldGroupEnableRequest = true;
            dev->coldGroupDisableRequest = false;
            dev->hotGroupEnableRequest = true;
            dev->hotGroupDisableRequest = false;
            dev->ahuFanEnableRequest = true;
            dev->airFlowEnableRequest = true;
            dev->airFlowDisableRequest = false;

            if (dev->standbyRequest) dev->status = MAIN_STATUS_STANDBY;
            else if (dev->heatingRequest) dev->status = MAIN_STATUS_HEATING;
            else if (dev->coolingRequest) dev->status = MAIN_STATUS_COOLING;
            else if (dev->ventilationRequest) dev->status = MAIN_STATUS_VENTILATION;
            break;

        case MAIN_STATUS_FAULT:
            LOGGER_LOG(&main_logger, LOG_LEVEL_DEBUG, "Fault.");
            dev->faultRequest = false;

            *error = true;
            dev->coldGroupEnableRequest = false;
            dev->coldGroupDisableRequest = true;
            dev->hotGroupEnableRequest = false;
            dev->hotGroupDisableRequest = true;
            dev->ahuFanEnableRequest = false;
            dev->airFlowEnableRequest = false;
            dev->airFlowDisableRequest = true;

            /* ST source of truth: only cumulativeOutputAction determines recovery. */
            if (dev->signalMgmt.cumulativeOutputAction == SIGNAL_OUTPUT_ACTION_NONE) {
                *error = false;
                dev->status = MAIN_STATUS_STANDBY;
            }
            break;
    }

    s_airDistrib.operationType = operationType;
    s_airDistrib.enable        = dev->airFlowEnableRequest && dev->airDistributionEnabled;
    s_airDistrib.clock1s       = clks->clock1s;
    AirDistributionController_Update(&s_airDistrib, dev);

    *done = dev->isCompleted;

    LOGGER_LOG(&main_logger, LOG_LEVEL_DEBUG, "Update HVAC devices.");
    DeviceManager_Update(dev, clks, operationType);

    /* Coherent post-device-update parameter snapshot. */
    ParameterLogger_Update(dev, clks, operationType);
}

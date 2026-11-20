#include "Main.h"
#include "DeviceDiagnostics.h"
#include "LoggerFacade.h"
#include "AirDistributionController.h"
#include "ParameterLogger.h"

static LoggerFacade              main_logger  = { .enable = true, .loggerName = MOQUI_APPLICATION_DEVICE_ID };
static DeviceDiagnostics         s_diags      = { .operationType = OPERATING_MODE_RUN };
static AirDistributionController s_airDistrib = {0};
/* Previous status, so that the FSM state is logged on change only */
static MainStatus                s_statusOld  = MAIN_STATUS_STANDBY;

void Main_Update(DeviceFacade *dev, const Clocks *clks, OperatingMode operationType, bool enable, bool deviceConfigContextResetRequest, bool *done, bool *error) {
    if (!enable) return;

    if (operationType == OPERATING_MODE_INIT) {
        LOGGER_LOG(&main_logger, LOG_LEVEL_DEBUG, "Setup and configuration of all devices.");
        dev->signalMgmt.operationType = SIGNAL_MGMT_OPERATING_MODE_RESET;
        dev->signalMgmt.loggerName = MOQUI_APPLICATION_DEVICE_ID;
        SignalMgmt_Update(&dev->signalMgmt);
        s_airDistrib.operationType = OPERATING_MODE_INIT;
        s_airDistrib.enable = false;
        s_airDistrib.clock1s = false;
        AirDistributionController_Update(&s_airDistrib, dev);
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
        s_airDistrib.operationType = OPERATING_MODE_INIT;
        s_airDistrib.enable = false;
        s_airDistrib.clock1s = false;
        AirDistributionController_Update(&s_airDistrib, dev);
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

        MainRuleEngine_Update(dev, clks, operationType, error);
    }

    /*
     * Preserve the originating phase while idling in Standby. A temporary thermal override of Drying
     * (Drying -> Cooling/Heating) keeps Drying as the originating phase: MainRuleEngine returns to Drying
     * from Cooling/Heating while lastStatus = Drying, so it must stay Drying for the whole override.
     */
    if (operationType == OPERATING_MODE_INIT) {
        dev->lastStatus = dev->status;
    } else if ((dev->status != MAIN_STATUS_STANDBY) &&
               !((dev->lastStatus == MAIN_STATUS_DRYING) &&
                 ((dev->status == MAIN_STATUS_COOLING) || (dev->status == MAIN_STATUS_HEATING)))) {
        dev->lastStatus = dev->status;
    }

    if (dev->faultRequest) {
        dev->status = MAIN_STATUS_FAULT;
    }

    switch (dev->status) {
        case MAIN_STATUS_STANDBY:
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

    /* Log the FSM state on change only: a message every scan would fill the log buffer. */
    if (dev->status != s_statusOld) {
        switch (dev->status) {
            case MAIN_STATUS_STANDBY:     LOGGER_LOG(&main_logger, LOG_LEVEL_INFO, "Standby."); break;
            case MAIN_STATUS_VENTILATION: LOGGER_LOG(&main_logger, LOG_LEVEL_INFO, "Ventilation."); break;
            case MAIN_STATUS_COOLING:     LOGGER_LOG(&main_logger, LOG_LEVEL_INFO, "Cooling."); break;
            case MAIN_STATUS_HEATING:     LOGGER_LOG(&main_logger, LOG_LEVEL_INFO, "Heating."); break;
            case MAIN_STATUS_DRYING:      LOGGER_LOG(&main_logger, LOG_LEVEL_INFO, "Drying."); break;
            case MAIN_STATUS_FAULT:       LOGGER_LOG(&main_logger, LOG_LEVEL_ERROR, "Fault."); break;
            default: break;
        }
        s_statusOld = dev->status;
    }

    s_airDistrib.operationType = operationType;
    s_airDistrib.enable        = dev->airFlowEnableRequest && dev->airDistributionEnabled;
    s_airDistrib.clock1s       = clks->clock1s;
    AirDistributionController_Update(&s_airDistrib, dev);

    *done = dev->isCompleted;

    DeviceManager_Update(dev, clks, operationType);

    /* Coherent post-device-update parameter snapshot. */
    ParameterLogger_Update(dev, clks, operationType);
}

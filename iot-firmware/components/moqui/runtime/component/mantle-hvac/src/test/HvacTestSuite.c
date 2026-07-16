#include "HvacTestSuite.h"
#include "LoggerFacade.h"
#include <string.h>

static LoggerFacade test_logger = { .enable = true, .loggerName = MOQUI_APPLICATION_DEVICE_ID };

/* --- Constants (faithful port of ST VAR CONSTANT block) --- */
#define HVAC_TIMEOUT     (500U)
#define T_SETPOINT       (4.0f)
#define T_HYS            (0.5f)
#define T_MIN            (2.0f)
#define T_MAX            (6.0f)
#define T_NORMAL         (4.0f)
#define T_HOT            (7.0f)
#define T_COLD           (1.0f)
#define RH_SET           (75.0f)
#define RH_HYS           (2.0f)
#define RH_MIN           (60.0f)
#define RH_MAX           (85.0f)
#define RH_NORMAL        (75.0f)
#define DUCT_MIN         (0.0f)
#define DUCT_MAX         (10.0f)
#define DUCT_RH_MAX      (95.0f)
#define DUCT_NORMAL      (5.0f)
#define DUCT_HOT         (12.0f)
#define DUCT_COLD        (-1.0f)

/* Convenience wrapper matching the ST call: main(operationType, enable) */
static void run(HvacTestSuite *s, OperatingMode op, bool enable)
{
    bool done  = false;
    bool error = false;
    Main_Update(&s->dev, &s->clks, op, enable, false, &done, &error);
}

/* Apply recipe defaults identical to the ST scan-preamble (lines 182-210) */
static void apply_defaults(HvacTestSuite *s)
{
    s->dev.tempSetpoint       = T_SETPOINT;
    s->dev.tempHysteresis     = T_HYS;
    s->dev.tempMin            = T_MIN;
    s->dev.tempMax            = T_MAX;
    s->dev.rhSetpoint         = RH_SET;
    s->dev.rhHysteresis       = RH_HYS;
    s->dev.rhMin              = RH_MIN;
    s->dev.rhMax              = RH_MAX;
    s->dev.rhControlEnabled    = false;
    s->dev.rhControlOnly       = false;
    s->dev.isCompleted         = false;
    s->dev.timeBreakEnabled       = false;
    s->dev.estimatedRuntime       = 0U;
    s->dev.minRuntime             = 0U;
    s->dev.ductTempMin            = DUCT_MIN;
    s->dev.ductTempMax            = DUCT_MAX;
    s->dev.ductRhMax              = DUCT_RH_MAX;
    /* Sensor defaults */
    s->dev.tempFeedback     = T_NORMAL;
    s->dev.rhFeedback       = RH_NORMAL;
    s->dev.ductTempFeedback = DUCT_NORMAL;
    s->dev.ductRhFeedback      = 70.0f;
}

/* Apply static device config (ST lines 218-281) — safe subset for test determinism */
static void apply_device_config(HvacTestSuite *s)
{
    s->dev.coldGlycolPump.actuatorId        = "HVAC_COLD_GLYCOL_PUMP";
    s->dev.coldGlycolPump.actuatorName      = "ColdGlycolPump";
    s->dev.coldGlycolPump.actuationType     = ACTUATOR_ACTUATION_SINGLE;
    s->dev.coldGlycolPump.feedbackType      = ACTUATOR_FEEDBACK_WITHOUT;
    s->dev.coldGlycolPump.model             = ACTUATOR_MODEL_ABBACH580;
    s->dev.coldGlycolPump.enableTime        = 1U;
    s->dev.coldGlycolPump.disableTime       = 1U;
    s->dev.coldGlycolPump.diagnosticsEnable = false;

    s->dev.hotGlycolPump.actuatorId         = "HVAC_HOT_GLYCOL_PUMP";
    s->dev.hotGlycolPump.actuatorName       = "HotGlycolPump";
    s->dev.hotGlycolPump.actuationType      = ACTUATOR_ACTUATION_SINGLE;
    s->dev.hotGlycolPump.feedbackType       = ACTUATOR_FEEDBACK_WITHOUT;
    s->dev.hotGlycolPump.model              = ACTUATOR_MODEL_ABBACH580;
    s->dev.hotGlycolPump.enableTime         = 1U;
    s->dev.hotGlycolPump.disableTime        = 1U;
    s->dev.hotGlycolPump.diagnosticsEnable  = false;

    s->dev.airFlow.actuatorId        = "HVAC_AIR_FLOW";
    s->dev.airFlow.actuatorName      = "AirFlow";
    s->dev.airFlow.actuationType     = ACTUATOR_ACTUATION_SINGLE;
    s->dev.airFlow.feedbackType      = ACTUATOR_FEEDBACK_WITHOUT;
    s->dev.airFlow.model             = ACTUATOR_MODEL_ABBACH580;
    s->dev.airFlow.enableTime        = 1U;
    s->dev.airFlow.disableTime       = 1U;
    s->dev.airFlow.diagnosticsEnable = false;
    s->dev.airFlowRef                = 50.0f;

    s->dev.coldGlycolValve.controlSystemId   = "HVAC_COLD_GLYCOL_VALVE";
    s->dev.coldGlycolValve.controlSystemName = "ColdGlycolValve";
    s->dev.coldGlycolValve.gain            = 1.0f;
    s->dev.coldGlycolValve.integrationTime = 0.0f;
    s->dev.coldGlycolValve.derivationTime  = 0.0f;
    s->dev.coldGlycolValve.outputMin       = 0.0f;
    s->dev.coldGlycolValve.outputMax       = 100.0f;

    s->dev.hotGlycolValve.controlSystemId   = "HVAC_HOT_GLYCOL_VALVE";
    s->dev.hotGlycolValve.controlSystemName = "HotGlycolValve";
    s->dev.hotGlycolValve.gain            = 1.0f;
    s->dev.hotGlycolValve.integrationTime = 0.0f;
    s->dev.hotGlycolValve.derivationTime  = 0.0f;
    s->dev.hotGlycolValve.outputMin       = 0.0f;
    s->dev.hotGlycolValve.outputMax       = 100.0f;

    s->dev.ahuFan.controlSystemId   = "HVAC_AHU_FAN";
    s->dev.ahuFan.controlSystemName = "AhuFan";
    s->dev.ahuFan.gain            = 1.0f;
    s->dev.ahuFan.integrationTime = 0.0f;
    s->dev.ahuFan.derivationTime  = 0.0f;
    s->dev.ahuFan.outputMin       = 0.0f;
    s->dev.ahuFan.outputMax       = 100.0f;
    s->dev.ahuFanSpeedSetpoint = 50.0f;

    s->dev.highFlowDamper.actuatorId         = "HVAC_HIGH_FLOW_DAMPER";
    s->dev.highFlowDamper.actuatorName       = "HighFlowDamper";
    s->dev.highFlowDamper.actuationType      = ACTUATOR_ACTUATION_SINGLE;
    s->dev.highFlowDamper.feedbackType       = ACTUATOR_FEEDBACK_WITHOUT;
    s->dev.highFlowDamper.model              = ACTUATOR_MODEL_ABBACH580;
    s->dev.highFlowDamper.enableTime         = 1U;
    s->dev.highFlowDamper.disableTime        = 1U;
    s->dev.highFlowDamper.diagnosticsEnable  = false;

    s->dev.lowFlowDamper.actuatorId          = "HVAC_LOW_FLOW_DAMPER";
    s->dev.lowFlowDamper.actuatorName        = "LowFlowDamper";
    s->dev.lowFlowDamper.actuationType       = ACTUATOR_ACTUATION_SINGLE;
    s->dev.lowFlowDamper.feedbackType        = ACTUATOR_FEEDBACK_WITHOUT;
    s->dev.lowFlowDamper.model               = ACTUATOR_MODEL_ABBACH580;
    s->dev.lowFlowDamper.enableTime          = 1U;
    s->dev.lowFlowDamper.disableTime         = 1U;
    s->dev.lowFlowDamper.diagnosticsEnable   = false;
}

void HvacTestSuite_Update(HvacTestSuite *suite)
{
    if (!suite->init) {
        memset(suite, 0, sizeof(HvacTestSuite));
        suite->init = true;
    }

    /* Watchdog */
    suite->cycles++;
    if ((suite->cycles > HVAC_TIMEOUT) && !suite->testDone) {
        suite->testFailed = true;
        suite->failStep   = suite->step;
        LOGGER_LOG(&test_logger, LOG_LEVEL_ERROR, "TIMEOUT at step %d", suite->step);
    }
    if (suite->testFailed) {
        return;
    }

    /* Warm-download reset */
    if (suite->testReset) {
        uint16_t i;
        suite->step   = 0;
        suite->cycles = 0;
        suite->testDone    = false;
        suite->testFailed  = false;
        suite->failStep    = 0;
        for (i = 1U; i <= HVAC_TEST_PASS_COUNT; i++) {
            suite->pass[i] = false;
        }
        suite->dev.status              = MAIN_STATUS_STANDBY;
        suite->dev.lastStatus          = MAIN_STATUS_STANDBY;
        suite->dev.isCompleted         = false;
        suite->dev.timeBreakEnabled    = false;
        suite->dev.actualRuntime       = 0U;
        suite->dev.actualBreakDuration = 0U;
        suite->dev.faultRequest        = false;
        suite->testReset = false;
    }

    /* Default recipe / sensor values (mirrors ST scan-preamble) */
    apply_defaults(suite);
    apply_device_config(suite);

    switch (suite->step) {
        /* Group 0: bootstrap — move to first real test */
        case 0:
            suite->dev.status = MAIN_STATUS_STANDBY;
            suite->cycles = 0U;
            suite->step   = 1U;
            break;

        /* pass[1]: operationType=Init sets status=Standby */
        case 1:
            suite->dev.status = MAIN_STATUS_COOLING; /* Force non-Standby */
            run(suite, OPERATING_MODE_INIT, true);
            if (suite->dev.status == MAIN_STATUS_STANDBY) {
                suite->pass[1] = true;
                suite->cycles  = 0U;
                suite->step    = 2U;
                LOGGER_LOG(&test_logger, LOG_LEVEL_INFO, "pass[1]: Init -> Standby");
            }
            break;

        /* pass[2]: enable=FALSE leaves status unchanged */
        case 2:
            suite->dev.status = MAIN_STATUS_COOLING;
            run(suite, OPERATING_MODE_RUN, false);
            if (suite->dev.status == MAIN_STATUS_COOLING) {
                suite->pass[2] = true;
                run(suite, OPERATING_MODE_INIT, true); /* Reset to Standby */
                suite->cycles = 0U;
                suite->step   = 3U;
                LOGGER_LOG(&test_logger, LOG_LEVEL_INFO, "pass[2]: enable=FALSE no-op");
            }
            break;

        /* pass[3]: Standby output function — all groups disabled */
        case 3:
            suite->dev.status     = MAIN_STATUS_STANDBY;
            suite->dev.lastStatus = MAIN_STATUS_STANDBY;
            run(suite, OPERATING_MODE_RUN, true);
            if (suite->dev.status == MAIN_STATUS_STANDBY &&
                !suite->dev.coldGroupEnableRequest &&
                !suite->dev.hotGroupEnableRequest  &&
                !suite->dev.ahuFanEnableRequest    &&
                !suite->dev.airFlowEnableRequest) {
                suite->pass[3] = true;
                suite->cycles  = 0U;
                suite->step    = 4U;
                LOGGER_LOG(&test_logger, LOG_LEVEL_INFO, "pass[3]: Standby output function OK");
            }
            break;

        /* pass[4]: Ventilation output function — AHU=ON, groups=OFF */
        case 4:
            suite->dev.status = MAIN_STATUS_VENTILATION;
            run(suite, OPERATING_MODE_RUN, true);
            if (suite->dev.status == MAIN_STATUS_VENTILATION &&
                !suite->dev.coldGroupEnableRequest &&
                !suite->dev.hotGroupEnableRequest  &&
                suite->dev.ahuFanEnableRequest     &&
                suite->dev.airFlowEnableRequest) {
                suite->pass[4] = true;
                suite->cycles  = 0U;
                suite->step    = 5U;
                LOGGER_LOG(&test_logger, LOG_LEVEL_INFO, "pass[4]: Ventilation output function OK");
            }
            break;

        /* pass[5]: Ventilation persists across multiple scans */
        case 5:
            run(suite, OPERATING_MODE_RUN, true);
            if ((suite->cycles >= 5U) && (suite->dev.status == MAIN_STATUS_VENTILATION)) {
                suite->pass[5] = true;
                suite->cycles  = 0U;
                suite->step    = 6U;
                LOGGER_LOG(&test_logger, LOG_LEVEL_INFO, "pass[5]: Ventilation persists");
            }
            break;

        /* pass[6]: Ventilation -> Standby on isCompleted */
        case 6:
            suite->dev.isCompleted = true;
            run(suite, OPERATING_MODE_RUN, true);
            if (suite->dev.status == MAIN_STATUS_STANDBY) {
                suite->pass[6] = true;
                suite->cycles  = 0U;
                suite->step    = 7U;
                LOGGER_LOG(&test_logger, LOG_LEVEL_INFO, "pass[6]: Ventilation -> Standby on isCompleted");
            }
            break;

        /* pass[7]: Cooling output function — cold=ON, hot=OFF */
        case 7:
            suite->dev.status      = MAIN_STATUS_COOLING;
            suite->dev.tempFeedback = T_HOT;
            run(suite, OPERATING_MODE_RUN, true);
            if (suite->dev.status == MAIN_STATUS_COOLING &&
                suite->dev.coldGroupEnableRequest  &&
                !suite->dev.hotGroupEnableRequest  &&
                suite->dev.ahuFanEnableRequest) {
                suite->pass[7] = true;
                suite->cycles  = 0U;
                suite->step    = 8U;
                LOGGER_LOG(&test_logger, LOG_LEVEL_INFO, "pass[7]: Cooling output function OK");
            }
            break;

        /* pass[8]: Cooling persists while T > tempMin */
        case 8:
            suite->dev.tempFeedback = T_HOT;
            run(suite, OPERATING_MODE_RUN, true);
            if ((suite->cycles >= 5U) && (suite->dev.status == MAIN_STATUS_COOLING)) {
                suite->pass[8] = true;
                suite->cycles  = 0U;
                suite->step    = 9U;
                LOGGER_LOG(&test_logger, LOG_LEVEL_INFO, "pass[8]: Cooling persists");
            }
            break;

        /* pass[9]: Cooling -> Standby at the lower thermostat threshold. */
        case 9:
            suite->dev.tempFeedback = T_SETPOINT - T_HYS;
            run(suite, OPERATING_MODE_RUN, true);
            if (suite->dev.status == MAIN_STATUS_STANDBY) {
                suite->pass[9] = true;
                suite->cycles  = 0U;
                suite->step    = 10U;
                LOGGER_LOG(&test_logger, LOG_LEVEL_INFO, "pass[9]: Cooling -> Standby at setpoint band");
            }
            break;

        /* pass[10]: Heating output function — hot=ON, cold=OFF */
        case 10:
            suite->dev.status      = MAIN_STATUS_HEATING;
            suite->dev.tempFeedback = T_COLD;
            run(suite, OPERATING_MODE_RUN, true);
            if (suite->dev.status == MAIN_STATUS_HEATING &&
                !suite->dev.coldGroupEnableRequest &&
                suite->dev.hotGroupEnableRequest   &&
                suite->dev.ahuFanEnableRequest) {
                suite->pass[10] = true;
                suite->cycles   = 0U;
                suite->step     = 11U;
                LOGGER_LOG(&test_logger, LOG_LEVEL_INFO, "pass[10]: Heating output function OK");
            }
            break;

        /* pass[11]: Heating persists while T < tempMax */
        case 11:
            suite->dev.tempFeedback = T_COLD;
            run(suite, OPERATING_MODE_RUN, true);
            if ((suite->cycles >= 5U) && (suite->dev.status == MAIN_STATUS_HEATING)) {
                suite->pass[11] = true;
                suite->cycles   = 0U;
                suite->step     = 12U;
                LOGGER_LOG(&test_logger, LOG_LEVEL_INFO, "pass[11]: Heating persists");
            }
            break;

        /* pass[12]: Heating -> Standby at the upper thermostat threshold. */
        case 12:
            suite->dev.tempFeedback = T_SETPOINT + T_HYS;
            run(suite, OPERATING_MODE_RUN, true);
            if (suite->dev.status == MAIN_STATUS_STANDBY) {
                suite->pass[12] = true;
                suite->cycles   = 0U;
                suite->step     = 13U;
                LOGGER_LOG(&test_logger, LOG_LEVEL_INFO, "pass[12]: Heating -> Standby at setpoint band");
            }
            break;

        /* pass[13]: Drying output function — cold=ON, hot=ON */
        case 13:
            suite->dev.status      = MAIN_STATUS_DRYING;
            suite->dev.tempFeedback = T_NORMAL;
            run(suite, OPERATING_MODE_RUN, true);
            if (suite->dev.status == MAIN_STATUS_DRYING &&
                suite->dev.coldGroupEnableRequest &&
                suite->dev.hotGroupEnableRequest  &&
                suite->dev.ahuFanEnableRequest) {
                suite->pass[13] = true;
                suite->cycles   = 0U;
                suite->step     = 14U;
                LOGGER_LOG(&test_logger, LOG_LEVEL_INFO, "pass[13]: Drying output function OK");
            }
            break;

        /* pass[14]: Drying persists while T in range */
        case 14:
            suite->dev.tempFeedback = T_NORMAL;
            run(suite, OPERATING_MODE_RUN, true);
            if ((suite->cycles >= 5U) && (suite->dev.status == MAIN_STATUS_DRYING)) {
                suite->pass[14] = true;
                suite->cycles   = 0U;
                suite->step     = 15U;
                LOGGER_LOG(&test_logger, LOG_LEVEL_INFO, "pass[14]: Drying persists");
            }
            break;

        /* pass[15]: Drying -> Cooling on tempOverMax */
        case 15:
            suite->dev.tempFeedback = T_HOT;
            run(suite, OPERATING_MODE_RUN, true);
            if (suite->dev.status == MAIN_STATUS_COOLING) {
                suite->pass[15] = true;
                suite->cycles   = 0U;
                suite->step     = 16U;
                LOGGER_LOG(&test_logger, LOG_LEVEL_INFO, "pass[15]: Drying -> Cooling on tempOverMax");
            }
            break;

        /* pass[16]: Cooling -> Drying when T back below tempMax (lastStatus=Drying) */
        case 16:
            suite->dev.lastStatus  = MAIN_STATUS_DRYING;
            suite->dev.tempFeedback = T_NORMAL;
            run(suite, OPERATING_MODE_RUN, true);
            if (suite->dev.status == MAIN_STATUS_DRYING) {
                suite->pass[16] = true;
                suite->cycles   = 0U;
                suite->step     = 17U;
                LOGGER_LOG(&test_logger, LOG_LEVEL_INFO, "pass[16]: Cooling -> Drying resume");
            }
            break;

        /* pass[17]: Drying -> Heating on tempUnderMin */
        case 17:
            suite->dev.tempFeedback = T_COLD;
            run(suite, OPERATING_MODE_RUN, true);
            if (suite->dev.status == MAIN_STATUS_HEATING) {
                suite->pass[17] = true;
                suite->cycles   = 0U;
                suite->step     = 18U;
                LOGGER_LOG(&test_logger, LOG_LEVEL_INFO, "pass[17]: Drying -> Heating on tempUnderMin");
            }
            break;

        /* pass[18]: Heating -> Drying when T restored (lastStatus=Drying) */
        case 18:
            suite->dev.lastStatus  = MAIN_STATUS_DRYING;
            suite->dev.tempFeedback = T_NORMAL;
            run(suite, OPERATING_MODE_RUN, true);
            if (suite->dev.status == MAIN_STATUS_DRYING) {
                suite->pass[18] = true;
                suite->cycles   = 0U;
                suite->step     = 19U;
                LOGGER_LOG(&test_logger, LOG_LEVEL_INFO, "pass[18]: Heating -> Drying resume");
            }
            break;

        /* pass[19]: Drying -> Standby on isCompleted */
        case 19:
            suite->dev.isCompleted = true;
            run(suite, OPERATING_MODE_RUN, true);
            if (suite->dev.status == MAIN_STATUS_STANDBY) {
                suite->pass[19] = true;
                suite->cycles   = 0U;
                suite->step     = 20U;
                LOGGER_LOG(&test_logger, LOG_LEVEL_INFO, "pass[19]: Drying -> Standby on isCompleted");
            }
            break;

        /* pass[20]: Drying -> Standby when timeBreakEnabled */
        case 20:
            run(suite, OPERATING_MODE_INIT, true); /* Clean slate */
            suite->dev.lastStatus       = MAIN_STATUS_DRYING;
            suite->dev.status           = MAIN_STATUS_DRYING;
            suite->dev.timeBreakEnabled = true;
            run(suite, OPERATING_MODE_RUN, true);
            if (suite->dev.status == MAIN_STATUS_STANDBY) {
                suite->pass[20] = true;
                suite->cycles   = 0U;
                suite->step     = 21U;
                LOGGER_LOG(&test_logger, LOG_LEVEL_INFO, "pass[20]: Drying -> Standby on timeBreakEnabled");
            }
            break;

        /* pass[21]: Standby -> Drying when break ends */
        case 21:
            suite->dev.lastStatus       = MAIN_STATUS_DRYING;
            suite->dev.timeBreakEnabled = false;
            suite->dev.rhControlOnly    = false;
            run(suite, OPERATING_MODE_RUN, true);
            if (suite->dev.status == MAIN_STATUS_DRYING) {
                suite->pass[21] = true;
                run(suite, OPERATING_MODE_INIT, true); /* Reset */
                suite->cycles = 0U;
                suite->step   = 22U;
                LOGGER_LOG(&test_logger, LOG_LEVEL_INFO, "pass[21]: Standby -> Drying on break end");
            }
            break;

        /* Regression: T=tempMax is above the thermostat band, not over the absolute limit. */
        case 22:
            suite->dev.status       = MAIN_STATUS_STANDBY;
            suite->dev.lastStatus   = MAIN_STATUS_COOLING;
            suite->dev.tempFeedback = T_MAX;
            run(suite, OPERATING_MODE_RUN, true);
            if (suite->dev.status == MAIN_STATUS_COOLING) {
                suite->pass[22] = true;
                run(suite, OPERATING_MODE_INIT, true); /* Reset for AirDistrib tests */
                suite->cycles   = 0U;
                suite->step     = 23U;
                LOGGER_LOG(&test_logger, LOG_LEVEL_INFO, "pass[22]: Standby -> Cooling re-activation");
            }
            break;

        /* pass[23]: AirDistrib disabled — no switching even after many clock1s ticks */
        case 23:
            suite->dev.status               = MAIN_STATUS_DRYING;
            suite->dev.tempFeedback         = T_NORMAL;
            suite->dev.airDistributionEnabled = false;
            suite->dev.setPointTimeHigh     = 2U;
            suite->dev.setPointTimeLow      = 2U;
            suite->clks.clock1s             = true;
            run(suite, OPERATING_MODE_RUN, true);
            suite->clks.clock1s             = false;
            if (suite->cycles >= 5U && !suite->dev.lowFlowDamperEnableRequest) {
                suite->pass[23] = true;
                suite->cycles   = 0U;
                suite->step     = 24U;
                LOGGER_LOG(&test_logger, LOG_LEVEL_INFO, "pass[23]: AirDistrib disabled, no switching");
            }
            break;

        /* pass[24]: AirDistrib enabled, Init->HighPhase: highFlowDamper=ON, lowFlowDamper=OFF */
        case 24:
            suite->dev.status                = MAIN_STATUS_DRYING;
            suite->dev.tempFeedback          = T_NORMAL;
            suite->dev.airDistributionEnabled = true;
            suite->dev.setPointTimeHigh      = 2U;
            suite->dev.setPointTimeLow       = 2U;
            suite->clks.clock1s              = false;
            run(suite, OPERATING_MODE_RUN, true);
            if (suite->dev.highFlowDamperEnableRequest && !suite->dev.lowFlowDamperEnableRequest) {
                suite->pass[24] = true;
                suite->cycles   = 0U;
                suite->step     = 25U;
                LOGGER_LOG(&test_logger, LOG_LEVEL_INFO, "pass[24]: AirDistrib Init->HighPhase");
            }
            break;

        /* pass[25]: HighPhase->TransitionToLow after setPointTimeHigh clock1s ticks */
        case 25:
            suite->dev.status                = MAIN_STATUS_DRYING;
            suite->dev.tempFeedback          = T_NORMAL;
            suite->dev.airDistributionEnabled = true;
            suite->clks.clock1s              = true;
            run(suite, OPERATING_MODE_RUN, true);
            suite->clks.clock1s              = false;
            if (suite->dev.lowFlowDamperEnableRequest && suite->dev.highFlowDamperDisableRequest) {
                suite->pass[25] = true;
                suite->cycles   = 0U;
                suite->step     = 26U;
                LOGGER_LOG(&test_logger, LOG_LEVEL_INFO, "pass[25]: HighPhase->TransitionToLow");
            }
            break;

        /* pass[26]: TransitionToLow->LowPhase after damper handshake (clock100ms) */
        case 26:
            suite->dev.status                = MAIN_STATUS_DRYING;
            suite->dev.tempFeedback          = T_NORMAL;
            suite->dev.airDistributionEnabled = true;
            suite->clks.clock100ms           = true;
            suite->clks.clock1s              = false;
            run(suite, OPERATING_MODE_RUN, true);
            suite->clks.clock100ms           = false;
            if (!suite->dev.lowFlowDamperEnableRequest && !suite->dev.highFlowDamperDisableRequest) {
                suite->pass[26] = true;
                suite->cycles   = 0U;
                suite->step     = 27U;
                LOGGER_LOG(&test_logger, LOG_LEVEL_INFO, "pass[26]: TransitionToLow->LowPhase");
            }
            break;

        /* pass[27]: LowPhase->TransitionToHigh after setPointTimeLow clock1s ticks */
        case 27:
            suite->dev.status                = MAIN_STATUS_DRYING;
            suite->dev.tempFeedback          = T_NORMAL;
            suite->dev.airDistributionEnabled = true;
            suite->clks.clock1s              = true;
            run(suite, OPERATING_MODE_RUN, true);
            suite->clks.clock1s              = false;
            if (suite->dev.highFlowDamperEnableRequest && suite->dev.lowFlowDamperDisableRequest) {
                suite->pass[27] = true;
                suite->dev.airDistributionEnabled = false;
                run(suite, OPERATING_MODE_INIT, true);
                suite->cycles   = 0U;
                suite->step     = 28U;
                LOGGER_LOG(&test_logger, LOG_LEVEL_INFO, "pass[27]: LowPhase->TransitionToHigh");
            }
            break;

        /* pass[28]: ductTempOverMax -> Fault */
        case 28:
            suite->dev.status           = MAIN_STATUS_DRYING;
            suite->dev.ductTempFeedback = DUCT_HOT;
            run(suite, OPERATING_MODE_RUN, true);
            if (suite->dev.status == MAIN_STATUS_FAULT) {
                suite->pass[28] = true;
                suite->cycles   = 0U;
                suite->step     = 29U;
                LOGGER_LOG(&test_logger, LOG_LEVEL_INFO, "pass[28]: ductTempOverMax -> Fault");
            }
            break;

        /* pass[29]: Fault persists while alarm is still active */
        case 29:
            suite->dev.ductTempFeedback = DUCT_HOT;
            run(suite, OPERATING_MODE_RUN, true);
            if ((suite->cycles >= 3U) && (suite->dev.status == MAIN_STATUS_FAULT)) {
                suite->pass[29] = true;
                suite->cycles   = 0U;
                suite->step     = 30U;
                LOGGER_LOG(&test_logger, LOG_LEVEL_INFO, "pass[29]: Fault persists under active alarm");
            }
            break;

        /* pass[30]: Fault -> Standby after Init (clears alarm) */
        case 30:
            /* ductTempFeedback reset to DUCT_NORMAL by apply_defaults() above */
            run(suite, OPERATING_MODE_INIT, true);
            if (suite->dev.status == MAIN_STATUS_STANDBY) {
                suite->pass[30] = true;
                suite->cycles   = 0U;
                suite->step     = 31U;
                LOGGER_LOG(&test_logger, LOG_LEVEL_INFO, "pass[30]: Fault -> Standby after Init");
            }
            break;

        /* pass[31]: ductTempUnderMin -> Fault */
        case 31:
            suite->dev.status           = MAIN_STATUS_DRYING;
            suite->dev.ductTempFeedback = DUCT_COLD;
            run(suite, OPERATING_MODE_RUN, true);
            if (suite->dev.status == MAIN_STATUS_FAULT) {
                suite->pass[31] = true;
                run(suite, OPERATING_MODE_INIT, true); /* Clear alarm + reset */
                suite->cycles = 0U;
                suite->step   = 32U;
                LOGGER_LOG(&test_logger, LOG_LEVEL_INFO, "pass[31]: ductTempUnderMin -> Fault");
            }
            break;

        /* pass[32]: Fault state — all groups disabled (safe state) */
        case 32:
            suite->dev.status           = MAIN_STATUS_DRYING;
            suite->dev.ductTempFeedback = DUCT_HOT;
            run(suite, OPERATING_MODE_RUN, true);
            if (suite->dev.status == MAIN_STATUS_FAULT &&
                !suite->dev.coldGroupEnableRequest &&
                !suite->dev.hotGroupEnableRequest  &&
                !suite->dev.ahuFanEnableRequest    &&
                !suite->dev.airFlowEnableRequest) {
                suite->pass[32] = true;
                run(suite, OPERATING_MODE_INIT, true); /* Clean up */
                suite->cycles   = 0U;
                suite->step     = 100U;
                LOGGER_LOG(&test_logger, LOG_LEVEL_INFO, "pass[32]: Fault safe state OK");
            }
            break;

        /* Done */
        case 100:
            suite->testDone = true;
            LOGGER_LOG(&test_logger, LOG_LEVEL_INFO, "All 32 HvacTestSuite scenarios PASSED!");
            break;

        default:
            suite->testFailed = true;
            suite->failStep   = suite->step;
            LOGGER_LOG(&test_logger, LOG_LEVEL_ERROR, "Unknown test step %d", suite->step);
            break;
    }

    /* Diagnostic mirrors */
    suite->mirStatus          = suite->dev.status;
    suite->mirColdGroupEnable = suite->dev.coldGroupEnableRequest;
    suite->mirHotGroupEnable  = suite->dev.hotGroupEnableRequest;
    suite->mirAhuFanEnable    = suite->dev.ahuFanEnableRequest;
    suite->mirAirFlowEnable   = suite->dev.airFlowEnableRequest;
    suite->mirFaultRequest    = suite->dev.faultRequest;
    suite->mirStandbyRequest  = suite->dev.standbyRequest;
    suite->mirCoolingRequest  = suite->dev.coolingRequest;
    suite->mirHeatingRequest  = suite->dev.heatingRequest;
    suite->mirDryingRequest   = suite->dev.dryingRequest;
    suite->mirTempInRange     = suite->dev.tempInRange;
    suite->mirTempOverMax     = suite->dev.tempOverMax;
    suite->mirTempUnderMin    = suite->dev.tempUnderMin;
    suite->mirDuctTempOverMax = suite->dev.ductTempOverMax;
    suite->mirDuctTempUnderMin = suite->dev.ductTempUnderMin;
    suite->mirTimeBreakEnabled = suite->dev.timeBreakEnabled;
    suite->mirLastStatus      = suite->dev.lastStatus;
    suite->mirActualRuntime   = suite->dev.actualRuntime;
}

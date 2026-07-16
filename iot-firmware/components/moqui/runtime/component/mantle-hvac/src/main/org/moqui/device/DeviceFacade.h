#ifndef DEVICE_FACADE_H
#define DEVICE_FACADE_H

#include <stdint.h>
#include <stdbool.h>
#include "Actuator.h"
#include "ProcessPid.h"  /* provides both Pid (inner) and ProcessPid (full FB) */
#include "MainStatus.h"
#include "SignalMgmt.h"

typedef struct {
    // Setpoints and limits
    float tempSetpoint;
    float tempHysteresis;
    float tempMin;
    float tempMax;
    float rhSetpoint;
    float rhHysteresis;
    float rhMin;
    float rhMax;
    // Feedback
    float tempFeedback;
    float rhFeedback;

    // Duct T+RH
    float ductTempMin;
    float ductTempMax;
    float ductRhMax;
    float ductTempFeedback;
    float ductRhFeedback;

    // Boolean predicates
    bool tempInRange;
    bool tempAtSetpoint;
    bool tempAboveSetpointBand;
    bool tempBelowSetpointBand;
    bool tempOverMax;
    bool tempOverMin;
    bool tempUnderMin;
    bool tempUnderMax;
    bool rhAtSetpoint;
    bool rhOverMax;
    bool rhUnderMin;
    bool rhOverMin;
    bool rhUnderMax;
    bool ductTempOverMax;
    bool ductTempUnderMin;
    bool ductRhOverMax;

    // Operating-mode flags
    bool rhControlEnabled;
    bool rhControlOnly;
    bool airMixingEnabled;
    bool airMixingFanEnableRequest;
    bool airMixingFanDisableRequest;
    Actuator airMixingFan;              /* Air mixing fan FB — port of dev.airMixingFan : Actuator */

    // Process cycle durations (seconds)
    uint32_t processEstimatedDuration;
    uint32_t processMinDuration;
    uint32_t processActualDuration;
    uint32_t processRemainingDuration;
    uint32_t estimatedRuntime;
    uint32_t minRuntime;
    uint32_t actualRuntime;
    uint32_t estimatedBreakDuration;
    uint32_t minBreakDuration;
    uint32_t actualBreakDuration;
    
    // Flags
    bool timeBreakEnabled;
    bool isCompleted;

    // Main FSM state and transition
    MainStatus status;
    MainStatus lastStatus;
    
    bool standbyRequest;
    bool ventilationRequest;
    bool coolingRequest;
    bool heatingRequest;
    bool dryingRequest;
    bool faultRequest;
    bool resetRequest;

    // HVAC devices
    bool coldGroupEnableRequest;
    bool coldGroupDisableRequest;
    Actuator coldGlycolPump;
    ProcessPid coldGlycolValve;   /* ST: coldGlycolValve : ProcessPid */

    bool hotGroupEnableRequest;
    bool hotGroupDisableRequest;
    Actuator hotGlycolPump;
    ProcessPid hotGlycolValve;    /* ST: hotGlycolValve : ProcessPid */

    bool ahuFanEnableRequest;
    float ahuFanSpeedSetpoint;
    float ahuFanSpeedFeedback;
    ProcessPid ahuFan;            /* ST: ahuFan : ProcessPid */

    bool airFlowEnableRequest;
    bool airFlowDisableRequest;
    float airFlowRef;
    float airFlowSpeedFeedback;
    Actuator airFlow;

    bool highFlowDamperEnableRequest;
    bool highFlowDamperDisableRequest;
    Actuator highFlowDamper;

    bool lowFlowDamperEnableRequest;
    bool lowFlowDamperDisableRequest;
    Actuator lowFlowDamper;

    SignalMgmt signalMgmt;
    bool airDistributionEnabled;
    uint16_t   setPointTimeHigh;   /* Cumulative time for high throw [s] — ST: setPointTimeHigh : UINT */
    uint16_t   setPointTimeLow;    /* Cumulative time for low throw  [s] — ST: setPointTimeLow  : UINT */

} DeviceFacade;

#endif // DEVICE_FACADE_H

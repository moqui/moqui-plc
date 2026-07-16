#include "MainRuleEngine.h"
#include <math.h>

void MainRuleEngine_Update(DeviceFacade *dev, const Clocks *clks, OperatingMode operationType, bool *error) {
    float tempDeviation;
    float rhDeviation;

    // Default safe state: return to standby
    dev->faultRequest = false;
    dev->standbyRequest = true;
    dev->heatingRequest = false;
    dev->coolingRequest = false;
    dev->ventilationRequest = false;
    dev->dryingRequest = false;

    *error = false;

    // Compute predicates
    dev->tempInRange = (dev->tempFeedback >= dev->tempMin + dev->tempHysteresis) && 
                       (dev->tempFeedback <= dev->tempMax - dev->tempHysteresis);
    
    tempDeviation = dev->tempFeedback - dev->tempSetpoint;
    if (tempDeviation < 0.0f) tempDeviation = -tempDeviation;
    dev->tempAtSetpoint = tempDeviation <= dev->tempHysteresis;
    /* Normal thermostat thresholds are independent from absolute alarm limits. */
    dev->tempAboveSetpointBand = dev->tempFeedback >= (dev->tempSetpoint + dev->tempHysteresis);
    dev->tempBelowSetpointBand = dev->tempFeedback <= (dev->tempSetpoint - dev->tempHysteresis);
    
    dev->tempOverMax = dev->tempFeedback > dev->tempMax;
    dev->tempOverMin = dev->tempFeedback > dev->tempMin;
    dev->tempUnderMin = dev->tempFeedback < dev->tempMin;
    dev->tempUnderMax = dev->tempFeedback < dev->tempMax;
    
    rhDeviation = dev->rhFeedback - dev->rhSetpoint;
    if (rhDeviation < 0.0f) rhDeviation = -rhDeviation;
    dev->rhAtSetpoint = rhDeviation <= dev->rhHysteresis;
    
    dev->rhOverMax = dev->rhFeedback > dev->rhMax - dev->rhHysteresis;
    dev->rhUnderMin = dev->rhFeedback < dev->rhMin + dev->rhHysteresis;
    dev->rhOverMin = dev->rhFeedback > dev->rhMin;
    dev->rhUnderMax = dev->rhFeedback < dev->rhMax;

    dev->ductTempOverMax = dev->ductTempFeedback > dev->ductTempMax;
    dev->ductTempUnderMin = dev->ductTempFeedback < dev->ductTempMin;
    dev->ductRhOverMax = dev->ductRhFeedback > dev->ductRhMax;

    // Process timing
    if (clks->clock1s) {
        if (dev->timeBreakEnabled && dev->status == MAIN_STATUS_STANDBY) {
            dev->processActualDuration += 1;
            dev->actualBreakDuration += 1;
            if (dev->estimatedBreakDuration > 0) {
                if (dev->actualBreakDuration >= dev->estimatedBreakDuration &&
                    dev->actualBreakDuration >= dev->minBreakDuration) {
                    dev->timeBreakEnabled = false;
                    dev->actualRuntime = 0;
                    dev->actualBreakDuration = 0;
                }
            }
        } else if (dev->status != MAIN_STATUS_STANDBY) {
            dev->processActualDuration += 1;
            dev->actualRuntime += 1;
            if (dev->estimatedRuntime > 0) {
                dev->processRemainingDuration = dev->processEstimatedDuration - dev->processActualDuration;
                if (!dev->timeBreakEnabled && 
                    dev->actualRuntime >= dev->estimatedRuntime &&
                    dev->actualRuntime >= dev->minRuntime) {
                    dev->timeBreakEnabled = true;
                    dev->actualBreakDuration = 0;
                }
            }
        } else if ((dev->lastStatus == MAIN_STATUS_COOLING || dev->lastStatus == MAIN_STATUS_HEATING) && !dev->isCompleted) {
            dev->processActualDuration += 1;
            if (dev->processEstimatedDuration > 0) {
                dev->processRemainingDuration = dev->processEstimatedDuration - dev->processActualDuration;
            }
        }

        if (dev->processEstimatedDuration > 0) {
            dev->isCompleted = (dev->processActualDuration >= dev->processEstimatedDuration) &&
                               (dev->processActualDuration >= dev->processMinDuration);
        }
    }

    // Fault gate
    if (*error || ((dev->signalMgmt.cumulativeOutputAction & 0x0002) != 0) ||
        dev->ductTempOverMax || dev->ductTempUnderMin) {
        dev->faultRequest = true;
        return;
    }

    // FSM Transitions
    switch (dev->status) {
        case MAIN_STATUS_STANDBY:
            if ((dev->lastStatus == MAIN_STATUS_COOLING || dev->lastStatus == MAIN_STATUS_STANDBY) && dev->tempAboveSetpointBand) {
                dev->standbyRequest = false;
                dev->coolingRequest = true;
            } else if ((dev->lastStatus == MAIN_STATUS_HEATING || dev->lastStatus == MAIN_STATUS_STANDBY) && dev->tempBelowSetpointBand) {
                dev->standbyRequest = false;
                dev->heatingRequest = true;
            } else if (dev->lastStatus == MAIN_STATUS_DRYING && !dev->timeBreakEnabled && !dev->isCompleted && dev->tempInRange && (!dev->rhControlOnly || (dev->rhControlEnabled && dev->rhOverMax))) {
                dev->standbyRequest = false;
                dev->dryingRequest = true;
            } else if (dev->lastStatus == MAIN_STATUS_STANDBY && !dev->tempOverMax && dev->rhOverMax) {
                dev->standbyRequest = false;
                dev->dryingRequest = true;
            } else if (dev->isCompleted) {
                dev->standbyRequest = true;
            }
            break;

        case MAIN_STATUS_VENTILATION:
            if (dev->isCompleted) {
                dev->standbyRequest = true;
            } else {
                dev->standbyRequest = false;
            }
            break;

        case MAIN_STATUS_COOLING:
            if (dev->tempBelowSetpointBand || dev->isCompleted) {
                dev->standbyRequest = true;
            } else if (dev->lastStatus == MAIN_STATUS_DRYING && (dev->tempUnderMax || (dev->rhControlEnabled && dev->rhOverMax && dev->tempUnderMax))) {
                dev->standbyRequest = false;
                dev->dryingRequest = true;
            } else {
                dev->standbyRequest = false;
            }
            break;

        case MAIN_STATUS_HEATING:
            if (dev->isCompleted || dev->tempAboveSetpointBand) {
                dev->standbyRequest = true;
            } else if ((dev->lastStatus == MAIN_STATUS_DRYING && dev->tempOverMin) || (dev->rhControlEnabled && dev->rhOverMax)) {
                dev->standbyRequest = false;
                dev->dryingRequest = true;
            } else {
                dev->standbyRequest = false;
            }
            break;

        case MAIN_STATUS_DRYING:
            if (dev->isCompleted) {
                dev->standbyRequest = true;
            } else if (!dev->rhControlOnly && dev->tempInRange && (dev->estimatedRuntime > 0) && (dev->actualRuntime > dev->estimatedRuntime)) {
                dev->standbyRequest = true;
            } else if (dev->rhControlOnly && dev->rhUnderMin && (dev->actualRuntime >= dev->minRuntime)) {
                dev->standbyRequest = true;
            } else if (dev->rhControlEnabled && dev->rhUnderMin) {
                dev->standbyRequest = true;
            } else if (dev->timeBreakEnabled) {
                dev->standbyRequest = true;
            } else if (dev->tempOverMax) {
                dev->standbyRequest = false;
                dev->coolingRequest = true;
            } else if (dev->tempUnderMin) {
                dev->standbyRequest = false;
                dev->heatingRequest = true;
            } else {
                dev->standbyRequest = false;
            }
            break;

        case MAIN_STATUS_FAULT:
            // Handled separately usually, but here just to be safe
            break;
    }
}

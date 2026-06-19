#include "ActuatorGroup.h"
#include <string.h>

void ActuatorGroup_Update(ActuatorGroup *grp, bool clockPulse) {
    if (!grp->init) {
        if ((grp->actuatorGroupId == NULL) && (grp->actuatorGroupName == NULL)) {
            grp->invalidConfig = true;
            return;
        }
        
        grp->loggerName = grp->actuatorGroupName ? grp->actuatorGroupName : grp->actuatorGroupId;
        grp->logger.enable = true;
        grp->logger.loggerName = grp->loggerName;
        grp->init = true;
    }

    LOGGER_LOG(&grp->logger, LOG_LEVEL_DEBUG, "Running actuator group.");

    grp->invalidConfig = (grp->actuatorNum < 1) || (grp->actuatorNum > ACTUATOR_GROUP_MAX_SIZE) ||
                         (grp->maxRunning < 1) || (grp->minRunning > grp->maxRunning) ||
                         (grp->maxRunning > grp->actuatorNum);
                         
    if (grp->invalidConfig) {
        grp->status = ACTUATOR_GROUP_STATUS_DISABLED;
        return;
    }

    /* Init sortedIdx */
    for (uint16_t i = 1; i <= grp->actuatorNum; i++) {
        if (grp->sortedIdx[i] == 0) {
            grp->sortedIdx[i] = i;
        }
    }

    grp->availableNum = 0;
    grp->runningNum = 0;
    for (uint16_t i = 1; i <= grp->actuatorNum; i++) {
        if (!grp->actuatorFault[i] && !grp->actuatorInterlocked[i]) {
            grp->availableNum++;
        }
        if (grp->actuatorEnabled[i]) {
            grp->runningNum++;
        }
    }
    grp->degraded = (grp->availableNum < grp->actuatorNum);
    grp->underMinimum = (grp->internalStatus == ACTUATOR_GROUP_STATUS_RUNNING) && (grp->runningNum < grp->minRunning);

    if (grp->autochange == ACTUATOR_GROUP_AUTOCHANGE_EVEN_WEAR && 
       (grp->internalStatus == ACTUATOR_GROUP_STATUS_RUNNING || grp->internalStatus == ACTUATOR_GROUP_STATUS_AUTOCHANGE)) {
        for (uint16_t i = 1; i <= grp->actuatorNum - 1; i++) {
            bool swapped = false;
            for (uint16_t j = 1; j <= grp->actuatorNum - i; j++) {
                bool faultJ = grp->actuatorFault[grp->sortedIdx[j]] || grp->actuatorInterlocked[grp->sortedIdx[j]];
                bool faultNext = grp->actuatorFault[grp->sortedIdx[j + 1]] || grp->actuatorInterlocked[grp->sortedIdx[j + 1]];
                
                if ((faultJ && !faultNext) || 
                    (!faultJ && !faultNext && grp->runHours[grp->sortedIdx[j]] > grp->runHours[grp->sortedIdx[j + 1]])) {
                    uint16_t tempIdx = grp->sortedIdx[j];
                    grp->sortedIdx[j] = grp->sortedIdx[j + 1];
                    grp->sortedIdx[j + 1] = tempIdx;
                    swapped = true;
                }
            }
            if (!swapped) break;
        }
    }

    grp->startTimerTrig = false;
    grp->stopTimerTrig = false;
    grp->autochangeTimerTrig = (grp->autochange == ACTUATOR_GROUP_AUTOCHANGE_FIXED_INTERVAL) && 
                               (grp->internalStatus == ACTUATOR_GROUP_STATUS_RUNNING);

    switch (grp->internalStatus) {
        case ACTUATOR_GROUP_STATUS_DISABLED:
            grp->groupDisable = false;
            grp->autochangeActive = false;
            grp->autochangeStep = 0;

            if (grp->groupEnable && grp->availableNum >= grp->minRunning) {
                LOGGER_LOG(&grp->logger, LOG_LEVEL_DEBUG, "Actuator group running.");
                grp->groupEnable = false;
                grp->internalStatus = ACTUATOR_GROUP_STATUS_RUNNING;
            } else if (grp->groupEnable && grp->availableNum < grp->minRunning) {
                grp->groupEnable = false;
            }
            break;

        case ACTUATOR_GROUP_STATUS_RUNNING:
            grp->groupEnable = false;
            grp->autochangeActive = false;

            if (grp->groupDisable) {
                grp->groupDisable = false;
                for (uint16_t i = 1; i <= grp->actuatorNum; i++) {
                    if (grp->actuatorEnabled[i]) grp->disableRequests[i] = true;
                    grp->enableRequests[i] = false;
                }
                grp->internalStatus = ACTUATOR_GROUP_STATUS_STOPPING;
                LOGGER_LOG(&grp->logger, LOG_LEVEL_DEBUG, "Actuator group stopping.");
            } else {
                if (grp->runningNum < grp->minRunning) {
                    for (uint16_t i = 1; i <= grp->actuatorNum; i++) {
                        uint16_t idx = grp->sortedIdx[i];
                        if (!grp->actuatorEnabled[idx] && !grp->actuatorFault[idx] && 
                            !grp->actuatorInterlocked[idx] && !grp->enableRequests[idx]) {
                            grp->enableRequests[idx] = true;
                            break;
                        }
                    }
                }

                if (grp->runningNum >= grp->minRunning && grp->runningNum < grp->maxRunning && grp->runningNum <= grp->actuatorNum - 1) {
                    grp->startTimerTrig = (grp->demandSetpoint > grp->startPoints[grp->runningNum]);
                    if (grp->startTimer_Q) {
                        for (uint16_t i = 1; i <= grp->actuatorNum; i++) {
                            uint16_t idx = grp->sortedIdx[i];
                            if (!grp->actuatorEnabled[idx] && !grp->actuatorFault[idx] && 
                                !grp->actuatorInterlocked[idx] && !grp->enableRequests[idx]) {
                                grp->enableRequests[idx] = true;
                                break;
                            }
                        }
                        grp->startTimerTrig = false;
                    }
                }

                if (grp->runningNum > grp->minRunning && (grp->runningNum - 1) <= grp->actuatorNum - 1) {
                    grp->stopTimerTrig = (grp->demandSetpoint < grp->stopPoints[grp->runningNum - 1]);
                    if (grp->stopTimer_Q) {
                        for (uint16_t i = grp->actuatorNum; i >= 1; i--) {
                            uint16_t idx = grp->sortedIdx[i];
                            if (grp->actuatorEnabled[idx] && !grp->disableRequests[idx]) {
                                grp->disableRequests[idx] = true;
                                break;
                            }
                        }
                        grp->stopTimerTrig = false;
                    }
                }

                if (grp->autochange != ACTUATOR_GROUP_AUTOCHANGE_NONE && grp->autochange != ACTUATOR_GROUP_AUTOCHANGE_ALL_STOPPED && 
                    grp->runningNum > 0 && grp->demandSetpoint <= grp->autochangeLevel) {
                    
                    if (grp->autochange == ACTUATOR_GROUP_AUTOCHANGE_EVEN_WEAR) {
                        uint16_t minHoursIdx = 0, maxHoursIdx = 0;
                        for (uint16_t i = 1; i <= grp->actuatorNum; i++) {
                            if (!grp->actuatorFault[i] && !grp->actuatorInterlocked[i]) {
                                if (minHoursIdx == 0) minHoursIdx = i;
                                else if (grp->runHours[i] < grp->runHours[minHoursIdx]) minHoursIdx = i;
                                
                                if (maxHoursIdx == 0) maxHoursIdx = i;
                                else if (grp->runHours[i] > grp->runHours[maxHoursIdx]) maxHoursIdx = i;
                            }
                        }

                        if (minHoursIdx > 0 && maxHoursIdx > 0 && minHoursIdx != maxHoursIdx && 
                            (grp->runHours[maxHoursIdx] - grp->runHours[minHoursIdx]) > grp->maxWearImbalance &&
                            grp->actuatorEnabled[maxHoursIdx] && !grp->actuatorEnabled[minHoursIdx] &&
                            !grp->actuatorFault[minHoursIdx] && !grp->actuatorInterlocked[minHoursIdx]) {
                            
                            grp->autochangeStopIdx = maxHoursIdx;
                            grp->autochangeStartIdx = 0;
                            grp->autochangeStep = 1;
                            grp->disableRequests[grp->autochangeStopIdx] = true;
                            grp->internalStatus = ACTUATOR_GROUP_STATUS_AUTOCHANGE;
                        }
                    } else if (grp->autochange == ACTUATOR_GROUP_AUTOCHANGE_FIXED_INTERVAL) {
                        if (grp->autochangeTimer_Q) {
                            grp->autochangeStopIdx = 0;
                            for (uint16_t i = grp->actuatorNum; i >= 1; i--) {
                                if (grp->actuatorEnabled[grp->sortedIdx[i]]) {
                                    grp->autochangeStopIdx = grp->sortedIdx[i];
                                    break;
                                }
                            }
                            if (grp->autochangeStopIdx > 0) {
                                grp->autochangeStep = 1;
                                grp->disableRequests[grp->autochangeStopIdx] = true;
                                grp->internalStatus = ACTUATOR_GROUP_STATUS_AUTOCHANGE;
                            }
                            grp->autochangeTimerTrig = false;
                        }
                    } else if (grp->autochange == ACTUATOR_GROUP_AUTOCHANGE_EXTERNAL_TRIGGER) {
                        if (grp->autochangeTrigger && !grp->autochangeTrigOld) {
                            grp->autochangeStopIdx = 0;
                            for (uint16_t i = grp->actuatorNum; i >= 1; i--) {
                                if (grp->actuatorEnabled[grp->sortedIdx[i]]) {
                                    grp->autochangeStopIdx = grp->sortedIdx[i];
                                    break;
                                }
                            }
                            if (grp->autochangeStopIdx > 0) {
                                grp->autochangeStep = 1;
                                grp->disableRequests[grp->autochangeStopIdx] = true;
                                grp->internalStatus = ACTUATOR_GROUP_STATUS_AUTOCHANGE;
                            }
                        }
                    }
                }
            }
            break;

        case ACTUATOR_GROUP_STATUS_STOPPING:
            if (grp->runningNum == 0) {
                if (grp->autochange == ACTUATOR_GROUP_AUTOCHANGE_ALL_STOPPED) {
                    uint16_t tempIdx = grp->sortedIdx[1];
                    for (uint16_t i = 1; i < grp->actuatorNum; i++) {
                        grp->sortedIdx[i] = grp->sortedIdx[i + 1];
                    }
                    grp->sortedIdx[grp->actuatorNum] = tempIdx;
                }
                grp->internalStatus = ACTUATOR_GROUP_STATUS_DISABLED;
            }
            break;

        case ACTUATOR_GROUP_STATUS_AUTOCHANGE:
            LOGGER_LOG(&grp->logger, LOG_LEVEL_DEBUG, "Actuator group autochange.");
            grp->autochangeActive = true;
            grp->groupEnable = false;

            if (grp->groupDisable) {
                grp->groupDisable = false;
                for (uint16_t i = 1; i <= grp->actuatorNum; i++) {
                    if (grp->actuatorEnabled[i]) grp->disableRequests[i] = true;
                    grp->enableRequests[i] = false;
                }
                grp->internalStatus = ACTUATOR_GROUP_STATUS_STOPPING;
            } else {
                if (grp->autochangeStep == 1) {
                    if (!grp->actuatorEnabled[grp->autochangeStopIdx]) {
                        if (grp->autochange == ACTUATOR_GROUP_AUTOCHANGE_FIXED_INTERVAL || 
                            grp->autochange == ACTUATOR_GROUP_AUTOCHANGE_EXTERNAL_TRIGGER) {
                            for (uint16_t i = 1; i <= grp->actuatorNum; i++) {
                                if (grp->sortedIdx[i] == grp->autochangeStopIdx) {
                                    for (uint16_t j = i; j < grp->actuatorNum; j++) {
                                        grp->sortedIdx[j] = grp->sortedIdx[j + 1];
                                    }
                                    grp->sortedIdx[grp->actuatorNum] = grp->autochangeStopIdx;
                                    break;
                                }
                            }
                        }

                        grp->autochangeStartIdx = 0;
                        for (uint16_t i = 1; i <= grp->actuatorNum; i++) {
                            uint16_t idx = grp->sortedIdx[i];
                            if (!grp->actuatorEnabled[idx] && !grp->actuatorFault[idx] && !grp->actuatorInterlocked[idx]) {
                                grp->autochangeStartIdx = idx;
                                break;
                            }
                        }

                        if (grp->autochangeStartIdx > 0) {
                            grp->enableRequests[grp->autochangeStartIdx] = true;
                            grp->autochangeStep = 2;
                        } else {
                            grp->autochangeStep = 0;
                            grp->internalStatus = ACTUATOR_GROUP_STATUS_RUNNING;
                        }
                    }
                } else if (grp->autochangeStep == 2) {
                    if (grp->actuatorEnabled[grp->autochangeStartIdx]) {
                        grp->autochangeStep = 0;
                        grp->internalStatus = ACTUATOR_GROUP_STATUS_RUNNING;
                    }
                }
            }
            break;

        default:
            break;
    }

    /* Timer logic */
    if (clockPulse) {
        if (grp->startTimerTrig) {
            grp->startTimerAccumulator++;
            if (grp->startTimerAccumulator >= grp->startDelay) grp->startTimer_Q = true;
        } else {
            grp->startTimerAccumulator = 0;
            grp->startTimer_Q = false;
        }

        if (grp->stopTimerTrig) {
            grp->stopTimerAccumulator++;
            if (grp->stopTimerAccumulator >= grp->stopDelay) grp->stopTimer_Q = true;
        } else {
            grp->stopTimerAccumulator = 0;
            grp->stopTimer_Q = false;
        }

        if (grp->autochangeTimerTrig) {
            grp->autochangeTimerAccumulator++;
            if (grp->autochangeTimerAccumulator >= grp->autochangeInterval) grp->autochangeTimer_Q = true;
        } else {
            grp->autochangeTimerAccumulator = 0;
            grp->autochangeTimer_Q = false;
        }
    }

    grp->autochangeTrigOld = grp->autochangeTrigger;
    grp->status = grp->internalStatus;
}

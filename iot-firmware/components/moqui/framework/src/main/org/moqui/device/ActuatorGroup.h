#ifndef ACTUATOR_GROUP_H
#define ACTUATOR_GROUP_H

#include <stdint.h>
#include <stdbool.h>

#include "ActuatorGroupStatus.h"
#include "ActuatorGroupAutochange.h"
#include "LoggerFacade.h"
#include "MoquiConf.h"

/* ACTUATOR_GROUP_MAX_SIZE defined in MoquiConf.h */

typedef struct {
    /* VAR_IN_OUT (Pointers to arrays handled by caller) */
    bool *enableRequests;
    bool *disableRequests;

    /* VAR_INPUT */
    const char *actuatorGroupId;
    const char *actuatorGroupName;

    uint16_t actuatorNum;
    uint16_t minRunning;
    uint16_t maxRunning;

    float demandSetpoint;
    float startPoints[8];
    float stopPoints[8];

    uint32_t startDelay; /* in ticks/ms depending on clock */
    uint32_t stopDelay;  /* in ticks/ms depending on clock */

    ActuatorGroupAutochange autochange;
    uint32_t autochangeInterval; /* in ticks/ms */
    float maxWearImbalance;
    float autochangeLevel;
    bool autochangeTrigger;

    bool actuatorEnabled[ACTUATOR_GROUP_MAX_SIZE + 1]; /* 1-indexed for PLC parity */
    bool actuatorFault[ACTUATOR_GROUP_MAX_SIZE + 1];
    bool actuatorInterlocked[ACTUATOR_GROUP_MAX_SIZE + 1];
    float runHours[ACTUATOR_GROUP_MAX_SIZE + 1];

    bool groupEnable;
    bool groupDisable;

    /* VAR_OUTPUT */
    ActuatorGroupStatus status;
    uint16_t availableNum;
    uint16_t runningNum;
    bool degraded;
    bool underMinimum;
    bool invalidConfig;
    bool autochangeActive;
    const char *loggerName;

    /* VAR (Internal State) */
    ActuatorGroupStatus internalStatus;
    uint16_t sortedIdx[ACTUATOR_GROUP_MAX_SIZE + 1];

    uint16_t autochangeStep;
    uint16_t autochangeStopIdx;
    uint16_t autochangeStartIdx;
    bool autochangeTrigOld;

    bool startTimerTrig;
    bool stopTimerTrig;
    bool autochangeTimerTrig;
    
    /* Simplistic timers for C port */
    uint32_t startTimerAccumulator;
    bool startTimer_Q;
    uint32_t stopTimerAccumulator;
    bool stopTimer_Q;
    uint32_t autochangeTimerAccumulator;
    bool autochangeTimer_Q;

    LoggerFacade logger;
    bool init;

} ActuatorGroup;

void ActuatorGroup_Update(ActuatorGroup *grp, bool clockPulse);

#endif /* ACTUATOR_GROUP_H */

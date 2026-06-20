#ifndef WORK_EFFORT_H
#define WORK_EFFORT_H

#include <stdint.h>
#include "WorkEffortPurpose.h"
#include "WorkEffortType.h"

typedef struct {
    char workEffortId[32];
    char parentWorkEffortId[32];
    char rootWorkEffortId[32];
    WorkEffortType workEffortTypeEnumId;
    WorkEffortPurpose purposeEnumId;
    char workTypeEnumId[32];
    char ownerPartyId[32];
    char statusId[32];
    char statusFlowId[32];
    int16_t priority;
    char topic[64];
    int16_t percentComplete;
    int16_t revisionNumber;
    char workEffortName[64];
    char description[128];
    char location[64];
    char facilityId[32];
    uint64_t estimatedStartDate;
    uint64_t estimatedCompletionDate;
    uint64_t actualStartDate;
    uint64_t actualCompletionDate;
    uint32_t recurInterval;
    uint64_t lastUpdatedStamp;
    int16_t recurLimit;
    uint64_t recurEndDate;
    uint32_t minRetryTime;
    int16_t maxRetryCount;
    uint64_t allDayStart;
    uint64_t allDayEnd;
    uint32_t estimatedWorkTime;
    uint32_t estimatedSetupTime;
    uint32_t remainingWorkTime;
    uint32_t actualWorkTime;
    uint32_t actualSetupTime;
    uint32_t totalTimeAllowed;
    uint32_t estimatedWorkDuration;
    uint32_t actualWorkDuration;
    uint32_t actualBreakDuration;
    char timeUomId[16];
} WorkEffort;

#endif /* WORK_EFFORT_H */

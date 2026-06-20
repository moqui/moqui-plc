#ifndef EDGE_TRIG_STATUS_MGR_H
#define EDGE_TRIG_STATUS_MGR_H

#include <stdint.h>
#include <stdbool.h>
#include "EdgeTriggerStatus.h"

typedef struct {
    /* VAR_INPUT */
    bool execute;
    bool readyCondition;
    bool abortRequest;
    bool abortComplete;
    bool resetRequest;
    bool resetComplete;
    bool errorCondition;
    uint16_t timeLimit;
    uint16_t timeout;
    bool clock;

    /* VAR_OUTPUT */
    bool done;
    bool busy;
    bool error;
    int16_t errorId;
    bool aborted;
    bool activeCycle;

    /* VAR */
    EdgeTriggerStatus status;
    uint16_t timeLimitTimer;
    uint16_t timeoutTimer;
    bool prevExecute;

} EdgeTrigStatusMgr;

void EdgeTrigStatusMgr_Update(EdgeTrigStatusMgr *mgr);

#endif /* EDGE_TRIG_STATUS_MGR_H */

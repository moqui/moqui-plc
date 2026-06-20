#ifndef LEVEL_CTRL_STATUS_MGR_H
#define LEVEL_CTRL_STATUS_MGR_H

#include <stdint.h>
#include <stdbool.h>
#include "LevelCtrlStatus.h"

typedef struct {
    /* VAR_INPUT */
    bool enable;
    bool readyCondition;
    bool abortComplete;
    bool resetRequest;
    bool resetComplete;
    bool errorCondition;
    bool isContinuous;
    uint16_t timeLimit;
    uint16_t timeout;
    bool clock;

    /* VAR_OUTPUT */
    bool done;
    bool busy;
    bool error;
    int16_t errorId;
    bool activeCycle;

    /* VAR (Internal State) */
    LevelCtrlStatus status;
    uint16_t timeLimitTimer;
    uint16_t timeoutTimer;

} LevelCtrlStatusMgr;

void LevelCtrlStatusMgr_Update(LevelCtrlStatusMgr *mgr);

#endif /* LEVEL_CTRL_STATUS_MGR_H */

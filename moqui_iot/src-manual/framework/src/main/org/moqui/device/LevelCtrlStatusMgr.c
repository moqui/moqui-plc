#include "LevelCtrlStatusMgr.h"
#include "MoquiConf.h"

void LevelCtrlStatusMgr_Update(LevelCtrlStatusMgr *mgr) {
    if (mgr->clock) {
        if (mgr->timeLimit > 0 && mgr->status == LEVEL_CTRL_STATUS_EXECUTING) {
            if (mgr->timeLimitTimer > 0) {
                mgr->timeLimitTimer--;
            } else {
                mgr->timeLimitTimer = mgr->timeLimit;
            }
        }

        if (mgr->timeoutTimer > 0 && mgr->status == LEVEL_CTRL_STATUS_EXECUTING) {
            mgr->timeoutTimer--;
        }
    }

    switch (mgr->status) {
        case LEVEL_CTRL_STATUS_DORMANT:
            mgr->done = false;
            mgr->busy = false;
            mgr->error = false;
            mgr->errorId = 0;
            mgr->activeCycle = false;

            if (mgr->enable) {
                mgr->timeoutTimer = mgr->timeout;
                mgr->timeLimitTimer = mgr->timeLimit;
                mgr->status = LEVEL_CTRL_STATUS_EXECUTING;
            }
            break;

        case LEVEL_CTRL_STATUS_EXECUTING:
            mgr->busy = true;
            mgr->activeCycle = (mgr->timeLimit == 0) || (mgr->timeLimitTimer > 0);

            if (mgr->errorCondition || ((mgr->timeout > 0) && (mgr->timeoutTimer == 0))) {
                mgr->status = LEVEL_CTRL_STATUS_ERROR;
            } else if (!mgr->enable) {
                mgr->status = LEVEL_CTRL_STATUS_ABORTING;
            } else if (!mgr->isContinuous && mgr->readyCondition) {
                mgr->status = LEVEL_CTRL_STATUS_DONE;
            }
            break;

        case LEVEL_CTRL_STATUS_ABORTING:
            mgr->activeCycle = false;

            if (mgr->errorCondition || ((mgr->timeout > 0) && (mgr->timeoutTimer == 0))) {
                mgr->status = LEVEL_CTRL_STATUS_ERROR;
            } else if (mgr->abortComplete) {
                mgr->status = LEVEL_CTRL_STATUS_RESETTING;
            }
            break;

        case LEVEL_CTRL_STATUS_DONE:
            mgr->busy = false;
            mgr->done = true;
            mgr->activeCycle = false;

            if (!mgr->enable) {
                mgr->status = LEVEL_CTRL_STATUS_RESETTING;
            }
            break;

        case LEVEL_CTRL_STATUS_ERROR:
            mgr->busy = false;
            mgr->activeCycle = false;
            mgr->error = true;

            if (mgr->errorCondition) {
                mgr->errorId = STATUS_MGR_ERROR_EXTERNAL;
            } else {
                mgr->errorId = STATUS_MGR_ERROR_TIMEOUT;
            }

            if (mgr->resetRequest || !mgr->enable) {
                mgr->status = LEVEL_CTRL_STATUS_RESETTING;
            }
            break;

        case LEVEL_CTRL_STATUS_RESETTING:
            mgr->done = false;
            mgr->error = false;
            mgr->errorId = 0;
            mgr->activeCycle = false;

            if (mgr->resetComplete) {
                mgr->status = LEVEL_CTRL_STATUS_DORMANT;
            }
            break;

        default:
            break;
    }
}

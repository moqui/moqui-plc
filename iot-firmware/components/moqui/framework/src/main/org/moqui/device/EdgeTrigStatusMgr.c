#include "EdgeTrigStatusMgr.h"
#include "MoquiConf.h"

void EdgeTrigStatusMgr_Update(EdgeTrigStatusMgr *mgr) {
    if (mgr->clock) {
        if (mgr->timeLimit > 0 && mgr->status == EDGE_TRIGGER_STATUS_EXECUTING) {
            if (mgr->timeLimitTimer > 0) {
                mgr->timeLimitTimer--;
            } else {
                mgr->timeLimitTimer = mgr->timeLimit;
            }
        }

        if (mgr->timeoutTimer > 0 && mgr->status == EDGE_TRIGGER_STATUS_EXECUTING) {
            mgr->timeoutTimer--;
        }
    }

    switch (mgr->status) {
        case EDGE_TRIGGER_STATUS_DORMANT:
            mgr->done = false;
            mgr->busy = false;
            mgr->aborted = false;
            mgr->error = false;
            mgr->errorId = 0;
            mgr->activeCycle = false;

            if (mgr->execute && !mgr->prevExecute) {
                mgr->timeoutTimer = mgr->timeout;
                mgr->timeLimitTimer = mgr->timeLimit;
                mgr->status = EDGE_TRIGGER_STATUS_EXECUTING;
            }
            break;

        case EDGE_TRIGGER_STATUS_EXECUTING:
            mgr->busy = true;
            mgr->activeCycle = (mgr->timeLimit == 0) || (mgr->timeLimitTimer > 0);

            if (mgr->errorCondition || ((mgr->timeout > 0) && (mgr->timeoutTimer == 0))) {
                mgr->status = EDGE_TRIGGER_STATUS_ERROR;
            } else if (mgr->abortRequest) {
                mgr->status = EDGE_TRIGGER_STATUS_ABORTING;
            } else if (mgr->readyCondition) {
                mgr->status = EDGE_TRIGGER_STATUS_DONE;
            }
            break;

        case EDGE_TRIGGER_STATUS_ABORTING:
            mgr->activeCycle = false;

            if (mgr->errorCondition || ((mgr->timeout > 0) && (mgr->timeoutTimer == 0))) {
                mgr->status = EDGE_TRIGGER_STATUS_ERROR;
            } else if (mgr->abortComplete) {
                mgr->status = EDGE_TRIGGER_STATUS_ABORTED;
            }
            break;

        case EDGE_TRIGGER_STATUS_ABORTED:
            mgr->busy = false;
            mgr->aborted = true;

            if (mgr->resetRequest || !mgr->execute) {
                mgr->status = EDGE_TRIGGER_STATUS_RESETTING;
            }
            break;

        case EDGE_TRIGGER_STATUS_DONE:
            mgr->busy = false;
            mgr->done = true;
            mgr->activeCycle = false;

            if (mgr->resetRequest || !mgr->execute) {
                mgr->status = EDGE_TRIGGER_STATUS_RESETTING;
            }
            break;

        case EDGE_TRIGGER_STATUS_ERROR:
            mgr->busy = false;
            mgr->activeCycle = false;
            mgr->error = true;

            if (mgr->errorCondition) {
                mgr->errorId = STATUS_MGR_ERROR_EXTERNAL;
            } else {
                mgr->errorId = STATUS_MGR_ERROR_TIMEOUT;
            }

            if (mgr->resetRequest || !mgr->execute) {
                mgr->status = EDGE_TRIGGER_STATUS_RESETTING;
            }
            break;

        case EDGE_TRIGGER_STATUS_RESETTING:
            mgr->done = false;
            mgr->aborted = false;
            mgr->error = false;
            mgr->errorId = 0;
            mgr->activeCycle = false;

            if (mgr->resetComplete) {
                mgr->status = EDGE_TRIGGER_STATUS_DORMANT;
            }
            break;

        default:
            break;
    }

    mgr->prevExecute = mgr->execute;
}

#ifndef LEVEL_CTRL_STATUS_H
#define LEVEL_CTRL_STATUS_H

/* PLCopen level-controlled FB FSM states (faithful port of LevelCtrlStatus.st). */
typedef enum {
    LEVEL_CTRL_STATUS_DORMANT   = 0,
    LEVEL_CTRL_STATUS_EXECUTING = 1,
    LEVEL_CTRL_STATUS_DONE      = 2,
    LEVEL_CTRL_STATUS_ABORTING  = 3,
    LEVEL_CTRL_STATUS_RESETTING = 4,
    LEVEL_CTRL_STATUS_ERROR     = 5
} LevelCtrlStatus;

#endif /* LEVEL_CTRL_STATUS_H */

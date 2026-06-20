#ifndef EDGE_TRIGGER_STATUS_H
#define EDGE_TRIGGER_STATUS_H

/* PLCopen edge-triggered FB FSM states (faithful port of EdgeTriggerStatus.st). */
typedef enum {
    EDGE_TRIGGER_STATUS_DORMANT   = 0,
    EDGE_TRIGGER_STATUS_EXECUTING = 1,
    EDGE_TRIGGER_STATUS_DONE      = 2,
    EDGE_TRIGGER_STATUS_ABORTING  = 3,
    EDGE_TRIGGER_STATUS_ABORTED   = 4,
    EDGE_TRIGGER_STATUS_RESETTING = 5,
    EDGE_TRIGGER_STATUS_ERROR     = 6
} EdgeTriggerStatus;

#endif /* EDGE_TRIGGER_STATUS_H */

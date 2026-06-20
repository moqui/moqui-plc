#ifndef ACTUATOR_GROUP_STATUS_H
#define ACTUATOR_GROUP_STATUS_H

/* ActuatorGroup FSM states (faithful port of ActuatorGroupStatus.st). */
typedef enum {
    ACTUATOR_GROUP_STATUS_DISABLED   = 0, /* No actuators running; group not active */
    ACTUATOR_GROUP_STATUS_RUNNING    = 1, /* Active: demand-driven start/stop in progress */
    ACTUATOR_GROUP_STATUS_STOPPING   = 2, /* Transitional: shutting down all running actuators */
    ACTUATOR_GROUP_STATUS_AUTOCHANGE = 3  /* Transitional: rotating the priority order (stop old / start new) */
} ActuatorGroupStatus;

#endif /* ACTUATOR_GROUP_STATUS_H */

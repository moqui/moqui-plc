#ifndef ACTUATOR_STATUS_H
#define ACTUATOR_STATUS_H

typedef enum {
    ACTUATOR_STATUS_DISABLED,       /* Stable */
    ACTUATOR_STATUS_ENABLE_PHASE,   /* Unstable */
    ACTUATOR_STATUS_ENABLED,        /* Stable */
    ACTUATOR_STATUS_DISABLE_PHASE   /* Unstable */
} ActuatorStatus;

#endif /* ACTUATOR_STATUS_H */

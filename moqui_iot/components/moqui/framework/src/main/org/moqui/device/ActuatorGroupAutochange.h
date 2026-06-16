#ifndef ACTUATOR_GROUP_AUTOCHANGE_H
#define ACTUATOR_GROUP_AUTOCHANGE_H

/*
 * Priority-order rotation strategy for ActuatorGroup (faithful port of ActuatorGroupAutochange.st).
 * Corresponds to ABB ACH580 parameter 76.70 Autochange.
 */
typedef enum {
    ACTUATOR_GROUP_AUTOCHANGE_NONE             = 0, /* Autochange disabled; priority order is fixed */
    ACTUATOR_GROUP_AUTOCHANGE_EVEN_WEAR        = 1, /* Rotate when run-hour imbalance > maxWearImbalance */
    ACTUATOR_GROUP_AUTOCHANGE_FIXED_INTERVAL   = 2, /* Rotate every autochangeInterval when demand <= autochangeLevel */
    ACTUATOR_GROUP_AUTOCHANGE_EXTERNAL_TRIGGER = 3, /* Rotate on rising edge of autochangeTrigger when demand <= autochangeLevel */
    ACTUATOR_GROUP_AUTOCHANGE_ALL_STOPPED      = 4  /* Rotate whenever the group stops (all actuators off) */
} ActuatorGroupAutochange;

#endif /* ACTUATOR_GROUP_AUTOCHANGE_H */

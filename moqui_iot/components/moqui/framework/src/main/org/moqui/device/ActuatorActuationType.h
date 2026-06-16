#ifndef ACTUATOR_ACTUATION_TYPE_H
#define ACTUATOR_ACTUATION_TYPE_H

typedef enum {
    ACTUATOR_ACTUATION_SINGLE,          /* Single Actuation: Uses enable output only */
    ACTUATOR_ACTUATION_DOUBLE,          /* Double Actuation: enable/disable are pulses */
    ACTUATOR_ACTUATION_DOUBLE_NO_RETAIN /* Double Actuation: enable/disable are levels */
} ActuatorActuationType;

#endif /* ACTUATOR_ACTUATION_TYPE_H */

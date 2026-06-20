#ifndef ACTUATOR_FEEDBACK_TYPE_H
#define ACTUATOR_FEEDBACK_TYPE_H

typedef enum {
    ACTUATOR_FEEDBACK_WITHOUT,          /* No feedback */
    ACTUATOR_FEEDBACK_SINGLE_DISABLE,   /* Single Deactivation Feedback: Only disabledSensor */
    ACTUATOR_FEEDBACK_SINGLE_ENABLE,    /* Single Activation Feedback: Only enabledSensor */
    ACTUATOR_FEEDBACK_DOUBLE            /* Double Feedback: Both sensors */
} ActuatorFeedbackType;

#endif /* ACTUATOR_FEEDBACK_TYPE_H */

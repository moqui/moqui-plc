#ifndef ACTUATOR_MODEL_H
#define ACTUATOR_MODEL_H

/*
 * Actuator hardware model identifiers (faithful port of ActuatorModel.st).
 * Used to select protocol-specific control word mappings.
 */
typedef enum {
    ACTUATOR_MODEL_ABBACH580,    /* ABB ACH580 */
    ACTUATOR_MODEL_CTM700,       /* Control Techniques CM700 */
    ACTUATOR_MODEL_DANFOSS_FC102, /* Danfoss FC102 */
    ACTUATOR_MODEL_ABB_PSTX      /* ABB PSTX SoftStarter */
} ActuatorModel;

#endif /* ACTUATOR_MODEL_H */

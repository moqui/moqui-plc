#ifndef RAMP_TYPE_H
#define RAMP_TYPE_H

/* Ramp profile selection for setpoint generators (faithful port of RampType.st). */
typedef enum {
    RAMP_TYPE_LINEAR,      /* Linear ramp */
    RAMP_TYPE_S_SHAPED,    /* S-Shaped ramp */
    RAMP_TYPE_EXPONENTIAL, /* Exponential ramp */
    RAMP_TYPE_CUSTOM       /* Custom-defined ramp function */
} RampType;

#endif /* RAMP_TYPE_H */

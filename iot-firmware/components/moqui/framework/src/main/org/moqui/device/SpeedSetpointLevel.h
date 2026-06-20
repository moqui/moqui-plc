#ifndef SPEED_SETPOINT_LEVEL_H
#define SPEED_SETPOINT_LEVEL_H

/*
 * Motor speed setpoint level constants (faithful port of SpeedSetpointLevel.st).
 * Alternatively the speed setpoint can be a continuous analog output.
 */
typedef enum {
    SPEED_SETPOINT_ZERO    = 0,
    SPEED_SETPOINT_NOMINAL,
    SPEED_SETPOINT_MIN,
    SPEED_SETPOINT_MAX,
    SPEED_SETPOINT_JOGGING,
    SPEED_SETPOINT_SAFELY_LIMITED
} SpeedSetpointLevel;

#endif /* SPEED_SETPOINT_LEVEL_H */

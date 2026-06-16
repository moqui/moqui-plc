#ifndef ACTUATOR_H
#define ACTUATOR_H

#include <stdint.h>
#include <stdbool.h>

#include "ActuatorStatus.h"
#include "ActuatorType.h"
#include "ActuatorModel.h"
#include "ActuatorFeedbackType.h"
#include "ActuatorActuationType.h"
#include "OperatingMode.h"
#include "LoggerFacade.h"

/*
 * Generic binary actuator control automata, including mechanism diagnostics.
 * Faithful port of Actuator.st (FUNCTION_BLOCK Actuator).
 *
 * Nominal state trajectory:
 *   Disabled -> EnablePhase -> Enabled -> DisablePhase -> Disabled
 * Admissible cross-transitions:
 *   EnablePhase <-> DisablePhase
 *
 * Handshake-based control (mirrors VAR_IN_OUT in ST):
 *   The caller sets *enableRequest = true to start the actuator.
 *   The FB clears it to false when the enable phase is acknowledged.
 *   Monitoring the falling edge lets sequences advance deterministically.
 */
typedef struct {
    /* VAR_IN_OUT — caller holds the arrays; FB writes through the pointers */
    bool *enableRequest;
    bool *disableRequest;

    /* VAR_INPUT — actuator metadata */
    const char           *actuatorId;
    const char           *actuatorName;
    ActuatorActuationType actuationType;
    ActuatorFeedbackType  feedbackType;
    ActuatorModel         model;
    OperatingMode         operationType;

    /* VAR_INPUT — clock and timing */
    bool     clock;
    uint16_t enableTime;
    uint16_t disableTime;

    /* VAR_INPUT — preset and diagnostics */
    bool enablePreset;
    bool diagnosticsEnable;

    /* VAR_INPUT — status sensors */
    bool  enabledSensor;
    bool  disabledSensor;
    bool  externalFault;
    float ref;      /* Optional process reference */
    float feedback; /* Optional process feedback */

    /* VAR_OUTPUT — diagnostics and fault signals */
    bool        fault;
    bool        actuatorFault;
    bool        enabledSensorFault;
    bool        disabledSensorFault;
    bool        notInitialized;
    const char *loggerName;

    /* VAR_OUTPUT — actuation outputs */
    bool enable;
    bool disable;

    /* VAR — internal state */
    ActuatorStatus status;
    uint16_t       timer;
    bool           timeout;
    bool           enabled;  /* Internal logical feedback (derived from sensors / state) */
    bool           disabled; /* Internal logical feedback (derived from sensors / state) */

    /* Logger facade */
    LoggerFacade logger;

} Actuator;

void Actuator_Init(Actuator *self);
void Actuator_Update(Actuator *self);

#endif /* ACTUATOR_H */

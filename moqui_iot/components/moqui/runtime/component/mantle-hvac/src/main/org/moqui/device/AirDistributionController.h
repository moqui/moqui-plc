#ifndef AIR_DISTRIBUTION_CONTROLLER_H
#define AIR_DISTRIBUTION_CONTROLLER_H

/*
 * AirDistributionController — port of AirDistributionController.st
 *
 * Logical sequencer for alternating high/low air throw.
 *
 * - Cumulative timers advance only when operationType == Run AND enable == true.
 * - Timers are frozen (retained) during standby/pause — no reset.
 * - Make-Before-Break transition: the outgoing damper is closed before the
 *   incoming one opens, preventing overpressure peaks.  The asynchronous
 *   handshake works through the Actuator FB clearing the VAR_IN_OUT request
 *   flags once the physical maneuver completes.
 *
 * In ST this FB uses VAR_EXTERNAL (dev : DeviceFacade).
 * In C, dev is passed as a pointer parameter to _Update().
 */

#include <stdint.h>
#include <stdbool.h>
#include "AirDistributionControllerStatus.h"
#include "DeviceFacade.h"
#include "LoggerFacade.h"
#include "OperatingMode.h"

typedef struct {
    /* VAR_INPUT */
    OperatingMode operationType;
    bool          enable;  /* Local run permission (air flow running + air mixing on) */
    bool          clock1s; /* 1-second base clock pulse */

    /* VAR */
    LoggerFacade                  logger;
    AirDistributionControllerStatus status;
    uint16_t cumulatedTimeHigh;
    uint16_t cumulatedTimeLow;
    bool     loggerInit;
} AirDistributionController;

/*
 * Update one scan cycle.
 * dev is VAR_EXTERNAL in ST — passed as pointer here (no copy).
 */
void AirDistributionController_Update(AirDistributionController *ctrl,
                                      DeviceFacade              *dev);

#endif /* AIR_DISTRIBUTION_CONTROLLER_H */

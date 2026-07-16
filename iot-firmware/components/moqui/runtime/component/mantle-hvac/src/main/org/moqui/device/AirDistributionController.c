#include "AirDistributionController.h"

/* MISRA C:2012 Rule 15.5 deviation: guard-clause early return at Init mode. */

void AirDistributionController_Update(AirDistributionController *ctrl,
                                      DeviceFacade              *dev) {
    if (!ctrl->loggerInit) {
        ctrl->logger.enable = true;
        ctrl->logger.loggerName = "HVAC_AIR_GROUP";
        ctrl->loggerInit = true;
    }

    /* Initialisation or reset upon critical Stop */
    if (ctrl->operationType == OPERATING_MODE_INIT) {
        LOGGER_LOG(&ctrl->logger, LOG_LEVEL_DEBUG, "Init air distribution controller.");
        ctrl->status           = AIR_DIST_STATUS_INIT;
        ctrl->cumulatedTimeHigh = 0U;
        ctrl->cumulatedTimeLow  = 0U;
        dev->highFlowDamperEnableRequest  = true;
        dev->highFlowDamperDisableRequest = false;
        dev->lowFlowDamperEnableRequest   = false;
        dev->lowFlowDamperDisableRequest  = true;
        return;
    }

    /* Logic advances ONLY when in Run mode and locally enabled */
    if ((ctrl->operationType != OPERATING_MODE_RUN) || !ctrl->enable) {
        /* Standby / Pause: freeze all timers and requests — do nothing */
        return;
    }

    switch (ctrl->status) {

        case AIR_DIST_STATUS_INIT:
            dev->highFlowDamperEnableRequest  = true;
            dev->highFlowDamperDisableRequest = false;
            dev->lowFlowDamperEnableRequest   = false;
            dev->lowFlowDamperDisableRequest  = true;
            LOGGER_LOG(&ctrl->logger, LOG_LEVEL_DEBUG, "Enter high throw phase.");
            ctrl->status = AIR_DIST_STATUS_HIGH_PHASE;
            break;

        case AIR_DIST_STATUS_HIGH_PHASE:
            if (ctrl->clock1s) {
                ctrl->cumulatedTimeHigh++;
            }
            if ((dev->setPointTimeHigh > 0U) &&
                (ctrl->cumulatedTimeHigh >= dev->setPointTimeHigh)) {
                ctrl->cumulatedTimeHigh = 0U;
                /* Make-Before-Break: close high, open low */
                dev->highFlowDamperEnableRequest  = false;
                dev->highFlowDamperDisableRequest = true;
                dev->lowFlowDamperEnableRequest   = true;
                dev->lowFlowDamperDisableRequest  = false;
                LOGGER_LOG(&ctrl->logger, LOG_LEVEL_DEBUG, "Transition to low throw.");
                ctrl->status = AIR_DIST_STATUS_TRANSITION_TO_LOW;
            }
            break;

        case AIR_DIST_STATUS_TRANSITION_TO_LOW:
            /* Wait for the Actuator FB to clear both request flags, confirming
             * the physical maneuver is complete (asynchronous handshake). */
            if (!dev->highFlowDamperDisableRequest && !dev->lowFlowDamperEnableRequest) {
                LOGGER_LOG(&ctrl->logger, LOG_LEVEL_DEBUG, "Enter low throw phase.");
                ctrl->status = AIR_DIST_STATUS_LOW_PHASE;
            }
            break;

        case AIR_DIST_STATUS_LOW_PHASE:
            if (ctrl->clock1s) {
                ctrl->cumulatedTimeLow++;
            }
            if ((dev->setPointTimeLow > 0U) &&
                (ctrl->cumulatedTimeLow >= dev->setPointTimeLow)) {
                ctrl->cumulatedTimeLow = 0U;
                /* Make-Before-Break: close low, open high */
                dev->highFlowDamperEnableRequest  = true;
                dev->highFlowDamperDisableRequest = false;
                dev->lowFlowDamperEnableRequest   = false;
                dev->lowFlowDamperDisableRequest  = true;
                LOGGER_LOG(&ctrl->logger, LOG_LEVEL_DEBUG, "Transition to high throw.");
                ctrl->status = AIR_DIST_STATUS_TRANSITION_TO_HIGH;
            }
            break;

        case AIR_DIST_STATUS_TRANSITION_TO_HIGH:
            if (!dev->lowFlowDamperDisableRequest && !dev->highFlowDamperEnableRequest) {
                LOGGER_LOG(&ctrl->logger, LOG_LEVEL_DEBUG, "Enter high throw phase.");
                ctrl->status = AIR_DIST_STATUS_HIGH_PHASE;
            }
            break;

        default:
            break;
    }
}

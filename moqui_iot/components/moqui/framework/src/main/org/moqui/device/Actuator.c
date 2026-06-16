#include "Actuator.h"

#include <string.h>
#include <stdio.h>

/* MISRA C:2012 Rule 15.5 deviation: early returns used for guard clauses throughout. */

/* -------------------------------------------------------------------------
 * Internal helpers
 * ---------------------------------------------------------------------- */

static void update_feedback(Actuator *self)
{
    switch (self->feedbackType) {
        case ACTUATOR_FEEDBACK_DOUBLE:
            self->enabled  = self->enabledSensor;
            self->disabled = self->disabledSensor;
            break;

        case ACTUATOR_FEEDBACK_SINGLE_DISABLE:
            self->disabled = self->disabledSensor;
            self->enabled  = (!self->disabled) &&
                             ((self->status == ACTUATOR_STATUS_ENABLED) ||
                              ((self->status == ACTUATOR_STATUS_ENABLE_PHASE) && self->timeout));
            break;

        case ACTUATOR_FEEDBACK_SINGLE_ENABLE:
            self->enabled  = self->enabledSensor;
            self->disabled = (!self->enabled) &&
                             ((self->status == ACTUATOR_STATUS_DISABLED) ||
                              ((self->status == ACTUATOR_STATUS_DISABLE_PHASE) && self->timeout));
            break;

        case ACTUATOR_FEEDBACK_WITHOUT:
            self->enabled  = (self->status == ACTUATOR_STATUS_ENABLED) ||
                             ((self->status == ACTUATOR_STATUS_ENABLE_PHASE) && self->timeout);
            self->disabled = (self->status == ACTUATOR_STATUS_DISABLED) ||
                             ((self->status == ACTUATOR_STATUS_DISABLE_PHASE) && self->timeout);
            break;

        default:
            /* Unreachable: all enum values covered; treat as WithoutFeedback */
            self->enabled  = false;
            self->disabled = true;
            break;
    }
}

/* -------------------------------------------------------------------------
 * Actuator_Init  (mirrors the OperatingMode.Init branch in ST)
 * ---------------------------------------------------------------------- */

void Actuator_Init(Actuator *self)
{
    char nameBuf[128];

    if (self->operationType != OPERATING_MODE_INIT) {
        return;
    }

    /* Args validation */
    if ((self->actuatorId == NULL) && (self->actuatorName == NULL)) {
        self->notInitialized = true;
        return;
    }

    /* Logger facade init — format: "name[id]" matching the ST concat */
    (void)snprintf(nameBuf, sizeof(nameBuf), "%s[%s]",
                   (self->actuatorName != NULL) ? self->actuatorName : "",
                   (self->actuatorId   != NULL) ? self->actuatorId   : "");
    LoggerFacade_Init(&self->logger, self->actuatorName); /* tag for platform log */
    self->loggerName = self->logger.loggerName;

    LOGGER_LOG(&self->logger, LOG_LEVEL_DEBUG, "Actuator initialization.");

    /* Pre-elaboration for feedback polymorphism (init path) */
    switch (self->feedbackType) {
        case ACTUATOR_FEEDBACK_DOUBLE:
            self->enabled  = self->enabledSensor;
            self->disabled = self->disabledSensor;
            break;
        case ACTUATOR_FEEDBACK_SINGLE_ENABLE:
            self->enabled  = self->enabledSensor;
            self->disabled = !self->enabled;
            break;
        case ACTUATOR_FEEDBACK_SINGLE_DISABLE:
            self->disabled = self->disabledSensor;
            self->enabled  = !self->disabled;
            break;
        case ACTUATOR_FEEDBACK_WITHOUT:
            self->enabled  = self->enablePreset;
            self->disabled = !self->enabled;
            break;
        default:
            self->enabled  = false;
            self->disabled = true;
            break;
    }

    if (self->enableRequest  != NULL) { *self->enableRequest  = false; }
    if (self->disableRequest != NULL) { *self->disableRequest = false; }

    if (self->enablePreset) {
        LOGGER_LOG(&self->logger, LOG_LEVEL_DEBUG, "Actuator preset to enabled status.");
        self->enable = true;
        self->timer  = self->enableTime;

        if (self->enabled) {
            self->status         = ACTUATOR_STATUS_ENABLED;
            self->notInitialized = false;
        } else {
            self->status         = ACTUATOR_STATUS_ENABLE_PHASE;
            self->notInitialized = true;
        }
    } else {
        LOGGER_LOG(&self->logger, LOG_LEVEL_DEBUG, "Actuator preset to disabled status.");
        self->enable = false;
        self->timer  = self->disableTime;

        if (self->disabled) {
            self->status         = ACTUATOR_STATUS_DISABLED;
            self->notInitialized = false;
        } else {
            self->status         = ACTUATOR_STATUS_DISABLE_PHASE;
            self->notInitialized = true;
        }
    }
}

/* -------------------------------------------------------------------------
 * Actuator_Update  (mirrors the OperatingMode.Run body in ST)
 * ---------------------------------------------------------------------- */

void Actuator_Update(Actuator *self)
{
    bool reqEnable;
    bool reqDisable;

    if (self->notInitialized) {
        LOGGER_LOG(&self->logger, LOG_LEVEL_ERROR, "Actuator not initialized.");
    }

    LOGGER_LOG(&self->logger, LOG_LEVEL_DEBUG, "Running actuator.");

    /* Clock handler for diagnosis-oriented timing */
    if (self->clock && (self->timer > 0U)) {
        self->timer--;
    }

    /* Timeout computation */
    self->timeout = (self->timer == 0U);

    /* Pre-elaboration for feedback polymorphism */
    update_feedback(self);

    reqEnable  = (self->enableRequest  != NULL) ? *self->enableRequest  : false;
    reqDisable = (self->disableRequest != NULL) ? *self->disableRequest : false;

    /* Generic actuator FSM */
    switch (self->status) {
        case ACTUATOR_STATUS_DISABLED:
            LOGGER_LOG(&self->logger, LOG_LEVEL_DEBUG, "Actuator disabled.");
            if (self->disableRequest != NULL) { *self->disableRequest = false; }

            if (reqEnable) {
                LOGGER_LOG(&self->logger, LOG_LEVEL_DEBUG,
                           "The actuator received an enable request.");
                self->enable = true;
                self->timer  = self->enableTime;
                self->status = ACTUATOR_STATUS_ENABLE_PHASE;
            }
            break;

        case ACTUATOR_STATUS_ENABLE_PHASE:
            LOGGER_LOG(&self->logger, LOG_LEVEL_DEBUG, "Actuator in the enabling phase.");

            /* Admissible transition: EnablePhase -> DisablePhase */
            if (reqDisable) {
                LOGGER_LOG(&self->logger, LOG_LEVEL_DEBUG,
                           "The actuator received a disable request.");
                if (self->enableRequest != NULL) { *self->enableRequest = false; }
                self->enable = false;
                self->timer  = self->disableTime;
                self->status = ACTUATOR_STATUS_DISABLE_PHASE;
            } else if (self->enabled) {
                /* End of enable phase: by feedback or by timeout (no-feedback typology) */
                if (self->enableRequest != NULL) { *self->enableRequest = false; }
                self->timer  = 0U;
                self->status = ACTUATOR_STATUS_ENABLED;
            } else {
                /* waiting */
            }
            break;

        case ACTUATOR_STATUS_ENABLED:
            LOGGER_LOG(&self->logger, LOG_LEVEL_DEBUG, "Actuator enabled.");
            if (self->enableRequest != NULL) { *self->enableRequest = false; }

            if (reqDisable) {
                LOGGER_LOG(&self->logger, LOG_LEVEL_DEBUG,
                           "The actuator received a disable request.");
                self->enable = false;
                self->timer  = self->disableTime;
                self->status = ACTUATOR_STATUS_DISABLE_PHASE;
            }
            break;

        case ACTUATOR_STATUS_DISABLE_PHASE:
            LOGGER_LOG(&self->logger, LOG_LEVEL_DEBUG, "Actuator in the disabling phase.");

            /* Admissible transition: DisablePhase -> EnablePhase */
            if (reqEnable) {
                LOGGER_LOG(&self->logger, LOG_LEVEL_DEBUG,
                           "The actuator received an enable request.");
                if (self->disableRequest != NULL) { *self->disableRequest = false; }
                self->enable = true;
                self->timer  = self->enableTime;
                self->status = ACTUATOR_STATUS_ENABLE_PHASE;
            } else if (self->disabled) {
                /* End of disable phase: by feedback or by timeout (no-feedback typology) */
                if (self->disableRequest != NULL) { *self->disableRequest = false; }
                self->timer  = 0U;
                self->status = ACTUATOR_STATUS_DISABLED;
            } else {
                /* waiting */
            }
            break;

        default:
            /* Unreachable with a well-formed enum; reset to a safe state */
            self->status = ACTUATOR_STATUS_DISABLED;
            break;
    }

    /* -----------------------------------------------------------------------
     * Diagnostics handler.
     * Detectable faults under dynamic and static conditions.
     * -------------------------------------------------------------------- */
    self->disabledSensorFault = self->diagnosticsEnable &&
        (((!self->enable && !self->disabled && !self->enabled) ||
          (self->enable  &&  self->disabled &&  self->enabled)) && self->timeout);

    self->enabledSensorFault = self->diagnosticsEnable &&
        (((!self->enable &&  self->disabled &&  self->enabled) ||
          (self->enable  && !self->disabled && !self->enabled)) && self->timeout);

    self->actuatorFault = self->diagnosticsEnable &&
        (((!self->enable && !self->disabled &&  self->enabled) ||
          (self->enable  &&  self->disabled && !self->enabled)) && self->timeout);

    self->fault = self->disabledSensorFault || self->enabledSensorFault ||
                  self->actuatorFault       || self->externalFault;

    if (self->fault) {
        LOGGER_LOG(&self->logger, LOG_LEVEL_ERROR, "Fault diagnostics:");
    }
    if (self->disabledSensorFault) {
        LOGGER_LOG(&self->logger, LOG_LEVEL_ERROR, "Disabled sensor fault.");
    }
    if (self->enabledSensorFault) {
        LOGGER_LOG(&self->logger, LOG_LEVEL_ERROR, "Enabled sensor fault.");
    }
    if (self->actuatorFault) {
        LOGGER_LOG(&self->logger, LOG_LEVEL_ERROR, "Actuator fault.");
    }
    if (self->externalFault) {
        LOGGER_LOG(&self->logger, LOG_LEVEL_ERROR,
                   "External fault (e.g: Motor branch-circuit protection).");
    }

    /* -----------------------------------------------------------------------
     * Post-elaboration for actuation polymorphism.
     * -------------------------------------------------------------------- */
    switch (self->actuationType) {
        case ACTUATOR_ACTUATION_SINGLE:
            /* Nothing to do; use enable output only */
            break;

        case ACTUATOR_ACTUATION_DOUBLE:
            self->disable = !self->enable;
            break;

        case ACTUATOR_ACTUATION_DOUBLE_NO_RETAIN:
            self->enable  = self->enable  && (self->status == ACTUATOR_STATUS_ENABLE_PHASE);
            self->disable = !self->enable && (self->status == ACTUATOR_STATUS_DISABLE_PHASE);
            break;

        default:
            /* Unreachable with a well-formed enum */
            break;
    }
}

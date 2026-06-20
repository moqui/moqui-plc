#include "SignalMgmt.h"
#include <string.h>

/* MISRA C:2012 Rule 15.5 deviation: early returns used for guard clauses throughout. */

void SignalMgmt_Update(SignalMgmt *sig) {
    if ((sig->loggerName == NULL) || (strlen(sig->loggerName) == 0U)) {
        sig->error = true;
        return;
    }

    if (!sig->init) {
        sig->logger.enable = true;
        sig->logger.loggerName = sig->loggerName;
        sig->init = true;
    }

    switch (sig->operationType) {
        case SIGNAL_MGMT_OPERATING_MODE_RESET:
            LOGGER_LOG(&sig->logger, LOG_LEVEL_DEBUG, "Signal management reset.");
            for (uint16_t i = 1; i <= SIGNAL_LIST_MAX_SIZE; i++) {
                sig->signalList[i] = false;
            }
            sig->resetOld = false;
            sig->auxResetOld = false;
            sig->selectiveResetOld = false;
            sig->cumulativeOutputAction = SIGNAL_OUTPUT_ACTION_NONE;
            sig->activeCategory = SIGNAL_CATEGORY_INFORMATION;
            sig->resetEnable = false;
            sig->auxResetEnable = false;
            break;

        case SIGNAL_MGMT_OPERATING_MODE_PREPARE:
            LOGGER_LOG(&sig->logger, LOG_LEVEL_DEBUG, "Prepare: Init cumulative output bitmask for the current cycle.");
            
            sig->resetActivation = sig->reset && !sig->resetOld;
            sig->resetOld = sig->reset;
            
            sig->auxResetActivation = sig->auxReset && !sig->auxResetOld;
            sig->auxResetOld = sig->auxReset;
            
            sig->selectiveResetActivation = sig->selectiveResetTrigger && !sig->selectiveResetOld;
            sig->selectiveResetOld = sig->selectiveResetTrigger;
            
            sig->cumulativeOutputAction = SIGNAL_OUTPUT_ACTION_NONE;
            sig->activeCategory = SIGNAL_CATEGORY_INFORMATION;
            sig->resetEnable = false;
            sig->auxResetEnable = false;
            break;

        case SIGNAL_MGMT_OPERATING_MODE_PROCESS:
            LOGGER_LOG(&sig->logger, LOG_LEVEL_DEBUG, "Process signal: %d", sig->code);

            if (sig->code < 1 || sig->code > SIGNAL_LIST_MAX_SIZE) {
                sig->error = true;
                return;
            }

            switch (sig->category) {
                case SIGNAL_CATEGORY_ALARM:
                case SIGNAL_CATEGORY_ANOMALY:
                    sig->requiresManualReset = (sig->resetPol != RESET_POLICY_AUTO_RESET);
                    break;
                case SIGNAL_CATEGORY_WARNING:
                case SIGNAL_CATEGORY_INFORMATION:
                    sig->requiresManualReset = false;
                    break;
                default:
                    break;
            }

            if (sig->activationCondition && !sig->signalList[sig->code]) {
                sig->signalList[sig->code] = true;
                LOGGER_LOG(&sig->logger, LOG_LEVEL_FATAL, "Signal code: %d active.", sig->code);
            }

            if (!sig->activationCondition && sig->signalList[sig->code]) {
                if (!sig->requiresManualReset) {
                    sig->signalList[sig->code] = false;
                } else if (sig->resetActivation) {
                    sig->signalList[sig->code] = false;
                } else if (sig->auxResetActivation && sig->resetPol == RESET_POLICY_AUX_RESET) {
                    sig->signalList[sig->code] = false;
                } else if (sig->autoResetCondition && (
                           sig->resetPol == RESET_POLICY_AUTO_CONDITIONED_RESET ||
                           sig->resetPol == RESET_POLICY_AUTO_PROVISIONAL_RESET ||
                           sig->resetPol == RESET_POLICY_AUTO_PRIORITY_RESET)) {
                    sig->signalList[sig->code] = false;
                } else if (sig->selectiveResetActivation && (sig->selectiveResetCode == sig->code)) {
                    sig->signalList[sig->code] = false;
                }

                if (!sig->signalList[sig->code]) {
                    LOGGER_LOG(&sig->logger, LOG_LEVEL_DEBUG, "Signal code: %d reset.", sig->code);
                }
            }

            if (sig->signalList[sig->code]) {
                sig->cumulativeOutputAction |= sig->outputAction;
                LOGGER_LOG(&sig->logger, LOG_LEVEL_DEBUG, "Signal cumulative output: %lu", (unsigned long)sig->cumulativeOutputAction);

                if (sig->category < sig->activeCategory) {
                    sig->activeCategory = sig->category;
                }
            }

            if (sig->signalList[sig->code] && !sig->activationCondition && sig->requiresManualReset) {
                sig->resetEnable = true;
            }
            if (sig->signalList[sig->code] && !sig->activationCondition && sig->resetPol == RESET_POLICY_AUX_RESET) {
                sig->auxResetEnable = true;
            }
            break;

        default:
            break;
    }
}

#ifndef SIGNAL_MGMT_H
#define SIGNAL_MGMT_H

#include <stdint.h>
#include <stdbool.h>

#include "SignalCategory.h"
#include "ResetPolicy.h"
#include "SignalMgmtOperatingMode.h"
#include "SignalOutputAction.h"
#include "LoggerFacade.h"
#include "MoquiConf.h"

/* SIGNAL_LIST_MAX_SIZE defined in MoquiConf.h */

typedef struct {
    /* VAR_INPUT */
    SignalMgmtOperatingMode operationType;
    
    uint16_t code;
    SignalCategory category;
    ResetPolicy resetPol;
    SignalOutputAction outputAction;
    
    bool activationCondition;
    bool autoResetCondition;
    
    bool reset;
    bool auxReset;
    
    bool selectiveResetTrigger;
    uint16_t selectiveResetCode;
    
    const char *loggerName;

    /* VAR_OUTPUT */
    uint32_t cumulativeOutputAction;
    SignalCategory activeCategory;
    
    bool resetEnable;
    bool auxResetEnable;
    bool error;

    /* VAR (Internal State) */
    LoggerFacade logger;
    bool signalList[SIGNAL_LIST_MAX_SIZE + 1]; /* 1-indexed for PLC parity */
    
    bool resetOld;
    bool resetActivation;
    bool auxResetOld;
    bool auxResetActivation;
    bool selectiveResetOld;
    bool selectiveResetActivation;
    bool requiresManualReset;

    bool init;
} SignalMgmt;

void SignalMgmt_Update(SignalMgmt *sig);

#endif /* SIGNAL_MGMT_H */

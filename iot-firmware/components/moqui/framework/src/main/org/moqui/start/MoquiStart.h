#ifndef MOQUI_START_H
#define MOQUI_START_H

#include <stdint.h>
#include <stdbool.h>
#include "MoquiStartStatus.h"
#include "OperatingMode.h"
#include "Clocks.h"
#include "LoggerFacade.h"
#include "NetworkDiagnostics.h"
#include "ClockGeneration.h"
#include "InputSignalUpdate.h"
#include "OutputSignalUpdate.h"
#include "DeviceConfigMgmt.h"
/* #include "Main.h" // In real integration, include Main.h here */

typedef struct {
    /* VAR_INPUT */
    bool enable;
    bool init;
    bool error;
    bool reset;

    /* VAR_OUTPUT */
    bool allConfigLoaded;

    /* VAR */
    OperatingMode operationType;
    MoquiStartStatus status;
    LoggerFacade logger;
    NetworkDiagnostics runNetworkDgs;
    ClockGeneration clockGen;
    InputSignalUpdate inputProcessing;
    OutputSignalUpdate outputProcessing;
    DeviceConfigMgmt configMgmt;
    bool mainDone;
    bool mainDoneOld;
    bool deviceConfigContextResetRequest;
    bool mainInitPending;
    uint32_t retryCount;
    uint32_t retryTime;
    bool autoReset;
    
} MoquiStart;

void MoquiStart_Update(MoquiStart *start, Clocks *clks);

#endif /* MOQUI_START_H */

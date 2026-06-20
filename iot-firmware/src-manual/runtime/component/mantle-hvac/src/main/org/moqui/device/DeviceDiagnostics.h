#ifndef DEVICE_DIAGNOSTICS_H
#define DEVICE_DIAGNOSTICS_H

/*
 * DeviceDiagnostics — port of DeviceDiagnostics.st (FUNCTION_BLOCK DeviceDiagnostics).
 *
 * Runs the SignalMgmt engine for all HVAC device signals:
 *   1. Prepare cycle (clears cumulativeOutputAction)
 *   2. Process cycle for each signal in priority order
 *
 * In ST this FB uses VAR_EXTERNAL (dev : DeviceFacade).
 * In C, dev is passed as a pointer parameter to _Update().
 */

#include <stdbool.h>
#include "OperatingMode.h"
#include "DeviceFacade.h"

typedef struct {
    /* VAR_INPUT */
    OperatingMode operationType;

    /* VAR_OUTPUT */
    bool error;
} DeviceDiagnostics;

/* Update one scan cycle.  dev is VAR_EXTERNAL — passed as pointer. */
void DeviceDiagnostics_Update(DeviceDiagnostics *diags, DeviceFacade *dev);

#endif /* DEVICE_DIAGNOSTICS_H */

#ifndef OUTPUT_SIGNAL_UPDATE_H
#define OUTPUT_SIGNAL_UPDATE_H

#include "OperatingMode.h"
#include "LoggerFacade.h"

typedef struct {
    /* VAR_INPUT */
    OperatingMode operationType;

    /* Application hook — drive hardware outputs from DeviceFacade state.
     * Set device_facade to the application's DeviceFacade pointer.
     * If NULL, the FB is a no-op (simulation mode). */
    void (*writeOutputs)(const void *device_facade);
    void *device_facade;

    /* VAR */
    LoggerFacade logger;
    bool init;

} OutputSignalUpdate;

void OutputSignalUpdate_Update(OutputSignalUpdate *osu);

#endif /* OUTPUT_SIGNAL_UPDATE_H */

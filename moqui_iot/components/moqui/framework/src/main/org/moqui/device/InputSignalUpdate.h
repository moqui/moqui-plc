#ifndef INPUT_SIGNAL_UPDATE_H
#define INPUT_SIGNAL_UPDATE_H

#include "OperatingMode.h"
#include "LoggerFacade.h"

typedef struct {
    /* VAR_INPUT */
    OperatingMode operationType;

    /* Application hook — populate DeviceFacade from hardware I/O.
     * Set device_facade to the application's DeviceFacade pointer.
     * If NULL, the FB is a no-op (simulation mode). */
    void (*readInputs)(void *device_facade);
    void *device_facade;

    /* VAR */
    LoggerFacade logger;
    bool init;

} InputSignalUpdate;

void InputSignalUpdate_Update(InputSignalUpdate *isu);

#endif /* INPUT_SIGNAL_UPDATE_H */

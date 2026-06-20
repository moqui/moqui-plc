#ifndef REMOTE_IO_MODULE_DIAGNOSTICS_H
#define REMOTE_IO_MODULE_DIAGNOSTICS_H

#include <stdint.h>
#include <stdbool.h>
#include "FieldbusProtocol.h"

typedef struct {
    /* VAR_INPUT */
    const char *moduleName;

    /* VAR_OUTPUT */
    bool error;
    char diagnosisInfo[128];

    /* VAR */
    uint8_t byteArrayBuffer[2];
    uint8_t deviceState;
    uint8_t parameterState;

} RemoteIoModuleDiagnostics;

void RemoteIoModuleDiagnostics_Update(RemoteIoModuleDiagnostics *diag, FieldbusProtocol fieldbus);

#endif /* REMOTE_IO_MODULE_DIAGNOSTICS_H */

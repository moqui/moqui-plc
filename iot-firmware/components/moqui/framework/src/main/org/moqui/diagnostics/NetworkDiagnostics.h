#ifndef NETWORK_DIAGNOSTICS_H
#define NETWORK_DIAGNOSTICS_H

#include <stdbool.h>
#include "FieldbusProtocol.h"
#include "LoggerFacade.h"
#include "RemoteIoModuleDiagnostics.h"

typedef struct {
    /* VAR_OUTPUT */
    bool error;

    /* VAR */
    LoggerFacade logger;
    RemoteIoModuleDiagnostics diagnoseIoModule;
    bool init;

} NetworkDiagnostics;

void NetworkDiagnostics_Update(NetworkDiagnostics *net, FieldbusProtocol fieldbus);

#endif /* NETWORK_DIAGNOSTICS_H */

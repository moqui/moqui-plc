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
    /* Previous error, so that the network state is logged on change only */
    bool errorOld;

} NetworkDiagnostics;

void NetworkDiagnostics_Update(NetworkDiagnostics *net, FieldbusProtocol fieldbus);

#endif /* NETWORK_DIAGNOSTICS_H */

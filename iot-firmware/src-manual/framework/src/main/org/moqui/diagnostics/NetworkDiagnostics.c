#include "NetworkDiagnostics.h"
#include "platform.h"

void NetworkDiagnostics_Update(NetworkDiagnostics *net, FieldbusProtocol fieldbus) {
    (void)fieldbus;

    if (!net->init) {
        net->logger.enable = true;
        net->logger.loggerName = "RunNetworkDiagnostics";
        net->init = true;
    }

    LOGGER_LOG(&net->logger, LOG_LEVEL_DEBUG, "Network diagnostics");

    if (!pal_net_is_connected()) {
        LOGGER_LOG(&net->logger, LOG_LEVEL_WARN, "No active network interface");
        net->error = true;
        return; /* MISRA C:2012 Rule 15.5 deviation: guard clause early return. */
    }
    net->error = false;
}

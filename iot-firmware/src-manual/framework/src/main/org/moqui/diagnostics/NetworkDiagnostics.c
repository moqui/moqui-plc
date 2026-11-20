#include "NetworkDiagnostics.h"
#include "platform.h"

void NetworkDiagnostics_Update(NetworkDiagnostics *net, FieldbusProtocol fieldbus) {
    (void)fieldbus;

    if (!net->init) {
        net->logger.enable = true;
        net->logger.loggerName = MOQUI_APPLICATION_DEVICE_ID;
        net->init = true;
    }

    net->error = !pal_net_is_connected();
    /* Log the network state on change only */
    if (net->error && !net->errorOld) {
        LOGGER_LOG(&net->logger, LOG_LEVEL_WARN, "No active network interface");
    }
    if (net->errorOld && !net->error) {
        LOGGER_LOG(&net->logger, LOG_LEVEL_INFO, "Network diagnostics: no errors.");
    }
    net->errorOld = net->error;
}

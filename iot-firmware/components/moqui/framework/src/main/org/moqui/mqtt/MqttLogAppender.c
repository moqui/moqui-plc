#include "MqttLogAppender.h"
#include "MqttClient.h"
#include "ParametersToJsonMapper.h"
#include "MoquiConf.h"
#include <string.h>

/*
 * MqttLogAppender — port of MqttLogAppender.st.
 *
 * Publishes log events in batches of LOG_APPENDER_BATCH_SIZE to the
 * MOQUI_LOG_TOPIC ("moqui-log").  Each event is serialized individually
 * (one JSON object per message) and enqueued via MqttClient_PublishLog.
 *
 * The caller is responsible for filling logBuffer / logBufferSize before
 * setting execute = true (see LoggerFacade_DrainBuffer).
 *
 * MISRA C:2012 Rule 15.5 deviation: guard-clause early returns.
 */

void MqttLogAppender_Update(MqttLogAppender *appender) {
    uint16_t i;
    static char json_buf[MQTT_PUB_PAYLOAD_MAX];

    if (!appender->init) { appender->init = true; }

    if (!appender->execute) {
        appender->done    = false;
        appender->busy    = false;
        appender->error   = false;
        appender->errorId = 0;
        return;
    }

    if (!appender->logBuffer || appender->logBufferSize == 0U) { return; }

    if (!appender->busy) {
        appender->busy = true;
        appender->done = false;

        for (i = 0U;
             (i < appender->logBufferSize) && (i < (uint16_t)LOG_APPENDER_BATCH_SIZE);
             i++) {
            /* The gateway consumes the canonical map-of-events batch envelope. */
            memcpy(json_buf, "{\"1\":", 5U);
            if (serialize_log_event(&appender->logBuffer[i], json_buf + 5U, sizeof(json_buf) - 6U)) {
                size_t size = strlen(json_buf);
                json_buf[size] = '}';
                json_buf[size + 1U] = '\0';
                MqttClient_PublishLog(json_buf);
            } else {
                appender->error   = true;
                appender->errorId = 1;
            }
        }

        appender->done = true;
        appender->busy = false;
    }
}

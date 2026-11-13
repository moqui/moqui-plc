#include "MqttLogAppender.h"
#include "LoggerFacade.h"
#include "MqttClient.h"
#include "ParametersToJsonMapper.h"
#include "MoquiConf.h"
#include "platform.h"
#include <stdio.h>
#include <string.h>

/*
 * MqttLogAppender — port of MqttLogAppender.st and LogDispatcher.st.
 *
 * One call queues at most one message on MOQUI_LOG_TOPIC ("moqui-log") through
 * MqttClient_PublishLog. The keys are the record positions with a fixed width,
 * so a reader that sorts keys keeps the record order. A record that cannot be
 * serialized (a non-finite number) or that does not fit one message is
 * released and counted in discardedCount.
 *
 * MISRA C:2012 Rule 15.5 deviation: guard-clause early returns.
 */

static bool append_record(char *json, size_t max, size_t *len, uint16_t key, const LogEvent *ev) {
    static char record[MQTT_PUB_PAYLOAD_MAX];
    int n;
    if (!serialize_log_event(ev, record, sizeof(record))) { return false; }
    n = snprintf(json + *len, max - *len, "%s\"%03u\":%s", (key > 1U) ? "," : "", (unsigned)key, record);
    if ((n < 0) || ((size_t)n >= max - *len)) { json[*len] = '\0'; return false; }
    *len += (size_t)n;
    return true;
}

uint16_t MqttLogAppender_BuildPayload(const LogEvent *report, const LogEvent *records, uint16_t count,
                                      char *json, size_t max, uint16_t *keys) {
    size_t len = 1U;
    uint16_t key = 0U;
    uint16_t taken = 0U;

    if ((json == NULL) || (keys == NULL) || (max < 3U)) {
        if (keys != NULL) { *keys = 0U; }
        return 0U;
    }
    json[0] = '{';
    json[1] = '\0';
    /* Keep one byte for the closing brace. */
    if ((report != NULL) && append_record(json, max - 1U, &len, (uint16_t)(key + 1U), report)) { key++; }
    while ((records != NULL) && (taken < count) &&
           append_record(json, max - 1U, &len, (uint16_t)(key + 1U), &records[taken])) {
        key++;
        taken++;
    }
    json[len] = '}';
    json[len + 1U] = '\0';
    *keys = key;
    return taken;
}

void MqttLogAppender_Update(MqttLogAppender *appender, bool connected) {
    static LogEvent batch[LOG_APPENDER_BATCH_SIZE];
    static char json[MQTT_PUB_PAYLOAD_MAX];
    LogEvent report;
    const LogEvent *reportRef = NULL;
    uint16_t count = 0U;
    uint16_t taken;
    uint16_t keys = 0U;
    uint32_t drops;

    if (appender == NULL) { return; }
    appender->done = false;
    LoggerFacade_FlushRepeats();
    if (!connected) { return; }

    drops = LoggerFacade_DroppedCount();
    LoggerFacade_PeekBuffer(batch, (uint16_t)LOG_APPENDER_BATCH_SIZE, &count);
    if ((count == 0U) && (drops == appender->reportedDropCount)) { return; }

    /* The drop report goes first: it describes records missing before this batch. */
    if (drops != appender->reportedDropCount) {
        (void)memset(&report, 0, sizeof(report));
        (void)snprintf(report.logEventId, sizeof(report.logEventId), "dropped-%lu", (unsigned long)drops);
        (void)strncpy(report.loggerName, MOQUI_APPLICATION_DEVICE_ID, sizeof(report.loggerName) - 1U);
        report.level = LOG_LEVEL_WARN;
        report.marker = LOG_MARKER_HEALTH;
        report.logEventDate = pal_time_us() / 1000ULL;
        report.payloadType = LOG_PAYLOAD_TYPE_TEXT;
        (void)snprintf(report.payload.message, sizeof(report.payload.message),
                       "%lu log events dropped: log buffer full",
                       (unsigned long)(drops - appender->reportedDropCount));
        report.repeatCount = 1U;
        reportRef = &report;
    }

    taken = MqttLogAppender_BuildPayload(reportRef, batch, count, json, sizeof(json), &keys);
    if (keys == 0U) {
        /* The oldest record is not serializable (a non-finite number) or does not fit
         * even alone: it would block the ring, so release it and count it. */
        if (count > 0U) {
            LoggerFacade_ReleaseBuffer(1U);
            if (appender->discardedCount < UINT32_MAX) { appender->discardedCount++; }
        }
        return;
    }

    if (!MqttClient_PublishLog(json)) {
        /* Publish queue full: keep the records for a later cycle. */
        appender->error = true;
        appender->errorId = 1;
        return;
    }
    LoggerFacade_ReleaseBuffer(taken);
    if (keys > taken) { appender->reportedDropCount = drops; }
    if (appender->publishedCount <= UINT32_MAX - keys) { appender->publishedCount += keys; }
    appender->done = true;
    appender->error = false;
    appender->errorId = 0;
}

#ifndef MQTT_LOG_APPENDER_H
#define MQTT_LOG_APPENDER_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include "LogEvent.h"

/*
 * Port of MqttLogAppender.st and LogDispatcher.st for the single logger ring of
 * LoggerFacade.c. Called by the control task once per cycle.
 */
typedef struct {
    /* VAR_OUTPUT */
    bool done;     /* a batch was queued in this call */
    bool error;    /* the last batch could not be queued (publish queue full) */
    int16_t errorId;

    /* Diagnostics */
    uint32_t reportedDropCount; /* LoggerFacade_DroppedCount() already reported */
    uint32_t publishedCount;    /* records queued for publishing */
    uint32_t discardedCount;    /* records that cannot be serialized or do not fit one message */
} MqttLogAppender;

/*
 * Queue at most one MQTT message with up to LOG_APPENDER_BATCH_SIZE records of the
 * logger ring, as the map of events the device gateway reads:
 *   {"001":{...},"002":{...}}
 * The records are released from the ring only when the message was accepted by
 * the publish queue; while the broker is not connected nothing is taken.
 * Records refused by a full ring are reported by one record "N log events dropped".
 */
void MqttLogAppender_Update(MqttLogAppender *appender, bool connected);

/*
 * Build the payload of one message into json[max]: the optional drop report,
 * then as many of the count records as fit. Returns the number of records taken
 * (the report is not counted); *keys receives the entries written, report
 * included. When nothing fits, json is "{}" and *keys is 0.
 */
uint16_t MqttLogAppender_BuildPayload(const LogEvent *report, const LogEvent *records, uint16_t count,
                                      char *json, size_t max, uint16_t *keys);

#endif /* MQTT_LOG_APPENDER_H */

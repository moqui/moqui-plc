#ifndef LOGGER_FACADE_H
#define LOGGER_FACADE_H

#include <stdbool.h>
#include <stdint.h>
#include "LogLevel.h"
#include "LogEvent.h"
#include "MoquiConf.h"

/*
 * Logger with local circular buffer and duplicate suppression.
 * Faithful port of LoggerFacade.st.
 *
 * Divergence from ST (intentional):
 *   Every LoggerFacade writes one ring buffer of LOG_MAX_SIZE records, owned by
 *   the control task, instead of one LogRingBuffer per facade. MqttLogAppender,
 *   called by the same task, is its only consumer: it reads records with
 *   LoggerFacade_PeekBuffer and releases them with LoggerFacade_ReleaseBuffer
 *   once they are queued for publishing. Events are also printed on the
 *   platform console. Duplicate suppression compares an event with the last
 *   stored one of any facade ("last message repeated N times").
 *
 * As in ST:
 *   - events below the minimum level (LoggerFacade_SetMinLevel, default
 *     LOG_MIN_LEVEL_DEFAULT) are ignored;
 *   - when the ring is full a new record is refused and counted
 *     (LoggerFacade_DroppedCount); stored records are never overwritten;
 *   - an event equal to the last stored one within LOG_SUPPRESS_DURATION_MS is
 *     only counted, and later written as one summary record with
 *     repeatCount = repetitions.
 *
 * Thread safety: none needed — every function is called by the control task.
 * LoggerFacade_Init MUST be called before the first LOGGER_LOG invocation.
 */
typedef struct {
    bool        enable;
    const char *loggerName;
} LoggerFacade;

/*
 * Initialise a LoggerFacade instance.
 * loggerName must point to a string with static or caller-owned lifetime.
 */
void LoggerFacade_Init(LoggerFacade *logger, const char *loggerName);

/* Lowest level stored and printed (LOG_LEVEL_ALL = TRACE, LOG_LEVEL_OFF = none). */
void LoggerFacade_SetMinLevel(LogLevel level);
LogLevel LoggerFacade_GetMinLevel(void);

/*
 * Platform logging back-end — defined in LoggerFacade.c so that
 * headers remain free of platform-specific includes.
 */
void LoggerFacade_Log(const LoggerFacade *logger, LogLevel level, const char *message);

/*
 * Append a parameter-scoped numeric event. loggerName is the exact owning
 * Device.deviceId and source is the exact pre-existing Parameter.parameterId.
 */
void LoggerFacade_LogNumeric(const LoggerFacade *logger, LogLevel level,
                             const char *source, double numericValue);

/*
 * Convenience macro: mirrors the ST call pattern
 *   logger(message := '...', level := LogLevel.Debug)
 * Usage:
 *   LOGGER_LOG(&self->logger, LOG_LEVEL_DEBUG, "My message");
 *   LOGGER_LOG(&self->logger, LOG_LEVEL_DEBUG, "Value: %f", val);
 */
#define LOGGER_LOG(logger_ptr, lvl, fmt, ...)                          \
    do {                                                               \
        if ((logger_ptr)->enable) {                                    \
            LoggerFacade_LogFmt((logger_ptr), (lvl), (fmt), ##__VA_ARGS__); \
        }                                                              \
    } while (0)

void LoggerFacade_LogFmt(const LoggerFacade *logger, LogLevel level,
                         const char *fmt, ...);

/*
 * Copy up to maxLen of the oldest records into out[] without removing them;
 * *outCount receives the number copied. Release them with
 * LoggerFacade_ReleaseBuffer once they are queued for publishing.
 */
void LoggerFacade_PeekBuffer(LogEvent *out, uint16_t maxLen, uint16_t *outCount);

/* Remove the count oldest records (at most the records stored). */
void LoggerFacade_ReleaseBuffer(uint16_t count);

/* Records refused because the ring was full, since start. */
uint32_t LoggerFacade_DroppedCount(void);

/*
 * Write the pending repetition summary when its window has elapsed, even if no
 * further event is logged. MqttLogAppender calls it every cycle.
 */
void LoggerFacade_FlushRepeats(void);

#endif /* LOGGER_FACADE_H */

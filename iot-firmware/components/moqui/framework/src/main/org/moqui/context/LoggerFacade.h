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
 *   The ST LoggerFacade uses a LogRingBuffer and a VAR_EXTERNAL log source list
 *   to feed a central LogAppender. On IoT targets we map directly to the
 *   platform logging backend (e.g. ESP-IDF esp_log, Zephyr LOG_*) via the
 *   LOGGER_LOG macro. The ring-buffer / appender pipeline is replaced by the
 *   RTOS logging subsystem which already provides buffering and transport.
 *
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
 * Copy up to maxLen pending LogEvent entries from the internal ring buffer
 * into out[], then clear the buffer.  *outCount receives the number copied.
 * Call from the MQTT appender task before invoking MqttLogAppender_Update.
 */
void LoggerFacade_DrainBuffer(LogEvent *out, uint16_t maxLen, uint16_t *outCount);

#endif /* LOGGER_FACADE_H */

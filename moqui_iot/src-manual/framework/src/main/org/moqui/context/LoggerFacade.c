#include "LoggerFacade.h"
#include "platform.h"

#include <stdarg.h>
#include <stdio.h>
#include <string.h>

/* -----------------------------------------------------------------------
 * Internal ring buffer — feeds MqttLogAppender without RTOS dependencies.
 *
 * Capacity: 2 × LOG_APPENDER_BATCH_SIZE so the appender can always drain
 * a full batch even if new events arrive during the same scan cycle.
 * Overflow policy: oldest entry silently overwritten (best-effort IoT log).
 * Thread safety: not required — LoggerFacade_Log is called only from the
 * control task (Core 1); LoggerFacade_DrainBuffer is called from the same
 * task immediately before MqttLogAppender_Update.
 * ----------------------------------------------------------------------- */
#define LOG_RING_CAPACITY (LOG_APPENDER_BATCH_SIZE * 2U)

static LogEvent  s_ring[LOG_RING_CAPACITY];
static uint16_t  s_ring_head  = 0U; /* next write slot (modulo capacity) */
static uint16_t  s_ring_count = 0U; /* entries waiting to be drained */
static uint32_t  s_event_seq  = 0U; /* monotone counter for logEventId */

/* -----------------------------------------------------------------------
 * Public API
 * ----------------------------------------------------------------------- */

void LoggerFacade_Init(LoggerFacade *logger, const char *loggerName)
{
    if (logger == NULL) {
        return;
    }
    logger->loggerName = loggerName;
    logger->enable     = true;
}

void LoggerFacade_LogFmt(const LoggerFacade *logger, LogLevel level,
                         const char *fmt, ...)
{
    char    buf[256];
    va_list args;

    if ((logger == NULL) || (!logger->enable) || (fmt == NULL)) {
        return;
    }

    va_start(args, fmt);
    (void)vsnprintf(buf, sizeof(buf), fmt, args);
    va_end(args);

    LoggerFacade_Log(logger, level, buf);
}

void LoggerFacade_Log(const LoggerFacade *logger, LogLevel level,
                      const char *message)
{
    const char *tag;
    LogEvent   *ev;

    if ((logger == NULL) || (!logger->enable) || (message == NULL)) {
        return;
    }

    tag = (logger->loggerName != NULL) ? logger->loggerName : "moqui";

    /* Forward to platform logging backend (UART / RTT / serial console). */
    switch (level) {
        case LOG_LEVEL_TRACE:
        case LOG_LEVEL_DEBUG:
            printf("[D][%s] %s\n", tag, message);
            break;
        case LOG_LEVEL_INFO:
            printf("[I][%s] %s\n", tag, message);
            break;
        case LOG_LEVEL_WARN:
            printf("[W][%s] %s\n", tag, message);
            break;
        case LOG_LEVEL_ERROR:
        case LOG_LEVEL_FATAL:
            printf("[E][%s] %s\n", tag, message);
            break;
        case LOG_LEVEL_ALL:
        case LOG_LEVEL_OFF:
        default:
            break;
    }

    /* Push into ring buffer for MqttLogAppender. */
    ev = &s_ring[s_ring_head];

    s_event_seq++;
    (void)snprintf(ev->logEventId, sizeof(ev->logEventId), "%08lx", (unsigned long)s_event_seq);

    (void)strncpy(ev->loggerName, tag, sizeof(ev->loggerName) - 1U);
    ev->loggerName[sizeof(ev->loggerName) - 1U] = '\0';

    (void)strncpy(ev->source, tag, sizeof(ev->source) - 1U);
    ev->source[sizeof(ev->source) - 1U] = '\0';

    ev->level       = level;
    ev->marker      = LOG_MARKER_DIAGNOSTICS;
    ev->payloadType = LOG_PAYLOAD_TYPE_TEXT;
    ev->logEventDate = pal_time_us() / 1000ULL; /* ms since boot */
    ev->repeatCount  = 0U;

    (void)strncpy(ev->payload.message, message, sizeof(ev->payload.message) - 1U);
    ev->payload.message[sizeof(ev->payload.message) - 1U] = '\0';

    /* Advance head; overwrite oldest if full. */
    s_ring_head = (uint16_t)((s_ring_head + 1U) % LOG_RING_CAPACITY);
    if (s_ring_count < (uint16_t)LOG_RING_CAPACITY) {
        s_ring_count++;
    }
}

void LoggerFacade_DrainBuffer(LogEvent *out, uint16_t maxLen, uint16_t *outCount)
{
    uint16_t n;
    uint16_t tail;
    uint16_t i;

    if ((out == NULL) || (outCount == NULL) || (maxLen == 0U)) {
        if (outCount != NULL) { *outCount = 0U; }
        return;
    }

    n = (s_ring_count < maxLen) ? s_ring_count : maxLen;

    /* tail = oldest entry position */
    tail = (uint16_t)(((uint32_t)s_ring_head + LOG_RING_CAPACITY - s_ring_count)
                      % LOG_RING_CAPACITY);

    for (i = 0U; i < n; i++) {
        out[i] = s_ring[(tail + i) % LOG_RING_CAPACITY];
    }

    s_ring_count = 0U; /* drain clears; head stays for next writes */

    *outCount = n;
}

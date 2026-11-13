#include "LoggerFacade.h"
#include "platform.h"

#include <stdarg.h>
#include <stdio.h>
#include <string.h>

/* MISRA C:2012 Rule 15.5 deviation: guard-clause early returns. */

/* -----------------------------------------------------------------------
 * Ring buffer — feeds MqttLogAppender without RTOS dependencies.
 *
 * Capacity follows LOG_MAX_SIZE so one coherent parameter snapshot may span
 * multiple MQTT batches without losing entries.
 * Overflow policy: a new record is refused and counted; stored records are
 * never overwritten (as LogRingBuffer.st).
 * Thread safety: not required — logging, LoggerFacade_PeekBuffer and
 * LoggerFacade_ReleaseBuffer all run in the control task.
 * ----------------------------------------------------------------------- */
#define LOG_RING_CAPACITY (LOG_MAX_SIZE)

static LogEvent  s_ring[LOG_RING_CAPACITY];
static uint16_t  s_ring_read  = 0U; /* oldest stored record */
static uint16_t  s_ring_count = 0U; /* records stored, not yet released */
static uint32_t  s_ring_sequence = 0U; /* sequence of the last stored record */
static uint32_t  s_ring_dropped = 0U;  /* records refused because the ring was full */
static uint32_t  s_event_seq  = 0U; /* monotone counter for logEventId */
static LogLevel  s_min_level  = LOG_MIN_LEVEL_DEFAULT;

/* Duplicate suppression: last stored event and its repetitions not yet written. */
static LogEvent  s_last;
static bool      s_has_last = false;
static uint16_t  s_repeat_pending = 0U;
static uint64_t  s_last_repeat_ms = 0U;

static bool ring_push(const LogEvent *ev)
{
    uint16_t slot;

    if (s_ring_count >= (uint16_t)LOG_RING_CAPACITY) {
        if (s_ring_dropped < UINT32_MAX) { s_ring_dropped++; }
        return false;
    }
    slot = (uint16_t)(((uint32_t)s_ring_read + s_ring_count) % LOG_RING_CAPACITY);
    s_ring[slot] = *ev;
    s_ring_sequence++;
    s_ring[slot].sequence = s_ring_sequence;
    s_ring_count++;
    return true;
}

static bool level_enabled(LogLevel level)
{
    LogLevel min = (s_min_level == LOG_LEVEL_ALL) ? LOG_LEVEL_TRACE : s_min_level;
    if ((s_min_level == LOG_LEVEL_OFF) || (level > LOG_LEVEL_FATAL)) { return false; }
    return level >= min;
}

static bool same_event(const LogEvent *a, const LogEvent *b)
{
    if ((a->payloadType != b->payloadType) || (a->level != b->level) || (a->marker != b->marker) ||
        (strncmp(a->loggerName, b->loggerName, sizeof(a->loggerName)) != 0) ||
        (strncmp(a->source, b->source, sizeof(a->source)) != 0)) {
        return false;
    }
    switch (a->payloadType) {
        case LOG_PAYLOAD_TYPE_TEXT:
            return strncmp(a->payload.message, b->payload.message, sizeof(a->payload.message)) == 0;
        case LOG_PAYLOAD_TYPE_NUMERIC:
            return a->payload.numericValue == b->payload.numericValue;
        case LOG_PAYLOAD_TYPE_ENUM:
            return a->payload.enumValue == b->payload.enumValue;
        default:
            return false;
    }
}

/* Write the repetitions of the last stored event as one summary record. */
static void write_repeat_summary(void)
{
    LogEvent summary;
    size_t   len;

    if (s_repeat_pending == 0U) { return; }
    summary = s_last;
    summary.logEventId[sizeof(summary.logEventId) - 1U] = '\0';
    len = strlen(summary.logEventId);
    (void)snprintf(summary.logEventId + len, sizeof(summary.logEventId) - len, "-r");
    summary.logEventDate = s_last_repeat_ms;
    summary.repeatCount = s_repeat_pending;
    s_repeat_pending = 0U;
    (void)ring_push(&summary);
}

static void store_event(const LogEvent *ev)
{
    if ((s_repeat_pending > 0U) &&
        ((ev->logEventDate - s_last.logEventDate) >= (uint64_t)LOG_SUPPRESS_DURATION_MS)) {
        write_repeat_summary();
    }
    if (s_has_last && same_event(ev, &s_last) &&
        ((ev->logEventDate - s_last.logEventDate) < (uint64_t)LOG_SUPPRESS_DURATION_MS)) {
        if (s_repeat_pending < UINT16_MAX) { s_repeat_pending++; }
        s_last_repeat_ms = ev->logEventDate;
        return;
    }
    write_repeat_summary();
    s_has_last = ring_push(ev);
    if (s_has_last) { s_last = *ev; }
}

static void fill_identity(LogEvent *ev, const char *loggerName, const char *source, LogLevel level)
{
    s_event_seq++;
    (void)snprintf(ev->logEventId, sizeof(ev->logEventId), "%08lx", (unsigned long)s_event_seq);
    (void)strncpy(ev->loggerName, loggerName, sizeof(ev->loggerName) - 1U);
    ev->loggerName[sizeof(ev->loggerName) - 1U] = '\0';
    /* Empty source denotes a DeviceLog. */
    (void)strncpy(ev->source, source, sizeof(ev->source) - 1U);
    ev->source[sizeof(ev->source) - 1U] = '\0';
    ev->level        = level;
    ev->marker       = LOG_MARKER_DIAGNOSTICS;
    ev->logEventDate = pal_time_us() / 1000ULL; /* ms since boot */
    ev->repeatCount  = 1U;
    ev->sequence     = 0U;
}

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

void LoggerFacade_SetMinLevel(LogLevel level) { s_min_level = level; }

LogLevel LoggerFacade_GetMinLevel(void) { return s_min_level; }

void LoggerFacade_LogFmt(const LoggerFacade *logger, LogLevel level,
                         const char *fmt, ...)
{
    char    buf[256];
    va_list args;

    if ((logger == NULL) || (!logger->enable) || (fmt == NULL) || !level_enabled(level)) {
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
    LogEvent    ev;

    if ((logger == NULL) || (!logger->enable) || (message == NULL) || !level_enabled(level)) {
        return;
    }

    tag = (logger->loggerName != NULL) ? logger->loggerName : MOQUI_APPLICATION_DEVICE_ID;

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

    /* Store into the ring buffer for MqttLogAppender. */
    (void)memset(&ev, 0, sizeof(ev));
    fill_identity(&ev, tag, "", level);
    ev.payloadType = LOG_PAYLOAD_TYPE_TEXT;
    (void)strncpy(ev.payload.message, message, sizeof(ev.payload.message) - 1U);
    ev.payload.message[sizeof(ev.payload.message) - 1U] = '\0';
    store_event(&ev);
}

void LoggerFacade_LogNumeric(const LoggerFacade *logger, LogLevel level,
                             const char *source, double numericValue)
{
    LogEvent ev;

    if ((logger == NULL) || (!logger->enable) || !level_enabled(level) ||
        (logger->loggerName == NULL) || (source == NULL) || (source[0] == '\0')) {
        return;
    }

    (void)memset(&ev, 0, sizeof(ev));
    fill_identity(&ev, logger->loggerName, source, level);
    ev.payloadType = LOG_PAYLOAD_TYPE_NUMERIC;
    ev.payload.numericValue = numericValue;
    store_event(&ev);
}

void LoggerFacade_PeekBuffer(LogEvent *out, uint16_t maxLen, uint16_t *outCount)
{
    uint16_t n;
    uint16_t i;

    if ((out == NULL) || (outCount == NULL) || (maxLen == 0U)) {
        if (outCount != NULL) { *outCount = 0U; }
        return;
    }

    n = (s_ring_count < maxLen) ? s_ring_count : maxLen;
    for (i = 0U; i < n; i++) {
        out[i] = s_ring[((uint32_t)s_ring_read + i) % LOG_RING_CAPACITY];
    }
    *outCount = n;
}

void LoggerFacade_ReleaseBuffer(uint16_t count)
{
    uint16_t n = (count < s_ring_count) ? count : s_ring_count;
    /* Keep entries beyond the released ones for the next MQTT batch. */
    s_ring_read  = (uint16_t)(((uint32_t)s_ring_read + n) % LOG_RING_CAPACITY);
    s_ring_count = (uint16_t)(s_ring_count - n);
}

uint32_t LoggerFacade_DroppedCount(void) { return s_ring_dropped; }

void LoggerFacade_FlushRepeats(void)
{
    if ((s_repeat_pending > 0U) &&
        (((pal_time_us() / 1000ULL) - s_last.logEventDate) >= (uint64_t)LOG_SUPPRESS_DURATION_MS)) {
        write_repeat_summary();
    }
}

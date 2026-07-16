#include "ParametersToJsonMapper.h"
#include "MoquiConf.h"
#include <stdint.h>
#include <stdio.h>
#include <stddef.h>
#include <string.h>

/* Documentation-only Application-specific parameter-replication example.
 * MqttParameterPub is disabled by default. Generate and review a peer-PLC
 * replication projection before enabling it; do not reuse the inbound
 * live-write whitelist. Operational telemetry belongs to LogDispatcher. */
#if 0
/* -----------------------------------------------------------------------
 * Descriptor-table driven serializer for DeviceFacade.
 *
 * MISRA C:2012 Rule 11.3 deviation: pointer casts via (const uint8_t *) +
 * offsetof are required for generic field access.  All casts are to the
 * exact declared type of each field, so the access is well-defined.
 * ----------------------------------------------------------------------- */

typedef enum {
    FIELD_F32,
    FIELD_I32,  /* int, enum (<=32-bit) */
    FIELD_U32,
    FIELD_U16,
    FIELD_BOOL
} DevFieldType;

typedef struct {
    const char  *key;
    size_t       offset;
    DevFieldType type;
} DevFieldDesc;

/* ----- Descriptor table — one row per telemetry field -----
 * To add a field: append one line.  No serializer code changes. */
static const DevFieldDesc s_dev_fields[] = {
    /* FSM state */
    { "status",          offsetof(DeviceFacade, status),                    FIELD_I32  },
    /* Environment feedback */
    { "tempFb",          offsetof(DeviceFacade, tempFeedback),              FIELD_F32  },
    { "rhFb",            offsetof(DeviceFacade, rhFeedback),                FIELD_F32  },
    { "ductTempFb",      offsetof(DeviceFacade, ductTempFeedback),          FIELD_F32  },
    { "ductRhFb",        offsetof(DeviceFacade, ductRhFeedback),            FIELD_F32  },
    /* Current setpoints are useful telemetry; configuration writes remain inbound. */
    { "tempSp",          offsetof(DeviceFacade, tempSetpoint),              FIELD_F32  },
    { "rhSp",            offsetof(DeviceFacade, rhSetpoint),                FIELD_F32  },
    /* Duct safety predicates */
    { "ductTmpOver",     offsetof(DeviceFacade, ductTempOverMax),           FIELD_BOOL },
    { "ductTmpUnder",    offsetof(DeviceFacade, ductTempUnderMin),          FIELD_BOOL },
    { "ductRhOver",      offsetof(DeviceFacade, ductRhOverMax),             FIELD_BOOL },
    /* Actuator statuses */
    { "coldPump",        offsetof(DeviceFacade, coldGlycolPump.status),     FIELD_I32  },
    { "hotPump",         offsetof(DeviceFacade, hotGlycolPump.status),      FIELD_I32  },
    { "airFlow",         offsetof(DeviceFacade, airFlow.status),            FIELD_I32  },
    { "hiDamper",        offsetof(DeviceFacade, highFlowDamper.status),     FIELD_I32  },
    { "loDamper",        offsetof(DeviceFacade, lowFlowDamper.status),      FIELD_I32  },
    { "airMixFan",       offsetof(DeviceFacade, airMixingFan.status),       FIELD_I32  },
    /* PID outputs */
    { "coldValve",       offsetof(DeviceFacade, coldGlycolValve.outputActual), FIELD_F32 },
    { "hotValve",        offsetof(DeviceFacade, hotGlycolValve.outputActual),  FIELD_F32 },
    { "ahuFan",          offsetof(DeviceFacade, ahuFan.outputActual),          FIELD_F32 },
    /* Operating flags */
    { "airMixOn",        offsetof(DeviceFacade, airMixingEnabled),          FIELD_BOOL },
    { "airDistOn",       offsetof(DeviceFacade, airDistributionEnabled),    FIELD_BOOL },
    /* Fault */
    { "fault",           offsetof(DeviceFacade, faultRequest),              FIELD_BOOL },
};

#define DEV_FIELDS_COUNT ((size_t)(sizeof(s_dev_fields) / sizeof(s_dev_fields[0])))

/* -----------------------------------------------------------------------
 * Generic loop: produces {"k":v,"k":v,...}
 * ----------------------------------------------------------------------- */
bool serialize_device_facade(const DeviceFacade *dev, char *output_buffer, size_t max_len) {
    size_t n = 0U;
    size_t i;

    if (!dev || !output_buffer || max_len == 0U) { return false; }

    n += (size_t)snprintf(output_buffer + n, max_len - n, "{");

    for (i = 0U; i < DEV_FIELDS_COUNT; i++) {
        const DevFieldDesc *d = &s_dev_fields[i];
        /* MISRA C:2012 Rule 11.3 deviation: generic field access via descriptor table. */
        const void *fptr = (const void *)(((const uint8_t *)dev) + d->offset);
        bool is_last = (i == (DEV_FIELDS_COUNT - 1U));
        const char *sep = is_last ? "" : ",";
        int written = 0;

        switch (d->type) {
            case FIELD_F32:
                written = snprintf(output_buffer + n, max_len - n,
                                   "\"%s\":%.2f%s", d->key, *(const float *)fptr, sep);
                break;
            case FIELD_I32:
                written = snprintf(output_buffer + n, max_len - n,
                                   "\"%s\":%d%s", d->key, (int)(*(const int32_t *)fptr), sep);
                break;
            case FIELD_U32:
                written = snprintf(output_buffer + n, max_len - n,
                                   "\"%s\":%lu%s", d->key, (unsigned long)*(const uint32_t *)fptr, sep);
                break;
            case FIELD_U16:
                written = snprintf(output_buffer + n, max_len - n,
                                   "\"%s\":%u%s", d->key, (unsigned)*(const uint16_t *)fptr, sep);
                break;
            case FIELD_BOOL:
                written = snprintf(output_buffer + n, max_len - n,
                                   "\"%s\":%s%s", d->key,
                                   *(const bool *)fptr ? "true" : "false", sep);
                break;
            default:
                break;
        }

        if (written > 0) { n += (size_t)written; }
        if (n >= max_len - 2U) { break; } /* Leave room for closing brace */
    }

    if (n < max_len - 1U) {
        output_buffer[n++] = '}';
    }
    output_buffer[n] = '\0';
    return (n > 2U); /* At least "{}" written */
}
#endif

bool serialize_device_facade(const DeviceFacade *dev, char *output_buffer, size_t max_len) {
    (void)dev;
    (void)output_buffer;
    (void)max_len;
    return false;
}

/* -----------------------------------------------------------------------
 * Actuator snapshot (unchanged — no descriptor table needed, fixed struct)
 * ----------------------------------------------------------------------- */
bool serialize_actuator_state(const Actuator *actuator, char *output_buffer, size_t max_len) {
    int written;
    if (!actuator || !output_buffer || max_len == 0U) { return false; }
    written = snprintf(output_buffer, max_len,
        "{\"id\":\"%s\",\"name\":\"%s\",\"status\":%d,\"enabled\":%s,\"fault\":%s}",
        actuator->actuatorId   ? actuator->actuatorId   : "",
        actuator->actuatorName ? actuator->actuatorName : "",
        (int)actuator->status,
        actuator->enable ? "true" : "false",
        actuator->fault  ? "true" : "false");
    return (written > 0) && ((size_t)written < max_len);
}

/* -----------------------------------------------------------------------
 * PID snapshot
 * ----------------------------------------------------------------------- */
bool serialize_pid_state(const Pid *pid, char *output_buffer, size_t max_len) {
    int written;
    if (!pid || !output_buffer || max_len == 0U) { return false; }
    written = snprintf(output_buffer, max_len,
        "{\"sp\":%.3f,\"fb\":%.3f,\"out\":%.3f,\"ovf\":%s,\"lim\":%s}",
        pid->setpoint,
        pid->feedback,
        pid->outputActual,
        pid->overflow           ? "true" : "false",
        pid->outputLimitsActive ? "true" : "false");
    return (written > 0) && ((size_t)written < max_len);
}

/* -----------------------------------------------------------------------
 * LogEvent -> JSON
 * ----------------------------------------------------------------------- */
bool serialize_log_event(const LogEvent *ev, char *output_buffer, size_t max_len) {
    int written;
    if (!ev || !output_buffer || max_len == 0U) { return false; }
    written = snprintf(output_buffer, max_len,
        "{\"id\":\"%s\",\"logger\":\"%s\",\"level\":%d,"
        "\"marker\":%d,\"ts\":%llu,\"src\":\"%s\","
        "\"msg\":\"%s\",\"rpt\":%u}",
        ev->logEventId,
        ev->loggerName,
        (int)ev->level,
        (int)ev->marker,
        (unsigned long long)ev->logEventDate,
        ev->source,
        ev->payload.message,
        (unsigned)ev->repeatCount);
    return (written > 0) && ((size_t)written < max_len);
}

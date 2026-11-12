#include "JsonToParametersMapper.h"
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <math.h>
#include "JsonFields.h"

/*
 * MISRA C:2012 Rule 11.3 deviation: pointer casts via (uint8_t *) + offsetof
 * are required for descriptor-table-driven field writes.
 * All casts are to the exact declared type of each field.
 */

/* Approved HVAC live-parameter write surface. Keep keys aligned with
 * HVACDemoData.xml DeviceRequestItem.requestItemName values. */
typedef enum {
    MAP_F32,
    MAP_U16,
    MAP_U32,
    MAP_BOOL
} MapFieldType;

typedef struct {
    const char  *key;
    size_t       offset;
    MapFieldType type;
} MapDesc;

/* ----- Write mapping table — one row per receivable JSON key -----
 * To add a new parameter mapping: append one line. */
static const MapDesc s_mappings[] = {
    { "tempSetpoint",       offsetof(DeviceFacade, tempSetpoint),       MAP_F32  },
    { "tempHysteresis",     offsetof(DeviceFacade, tempHysteresis),     MAP_F32  },
    { "tempMin",            offsetof(DeviceFacade, tempMin),            MAP_F32  },
    { "tempMax",            offsetof(DeviceFacade, tempMax),            MAP_F32  },
    { "rhSetpoint",         offsetof(DeviceFacade, rhSetpoint),         MAP_F32  },
    { "rhHysteresis",       offsetof(DeviceFacade, rhHysteresis),       MAP_F32  },
    { "rhMin",              offsetof(DeviceFacade, rhMin),              MAP_F32  },
    { "rhMax",              offsetof(DeviceFacade, rhMax),              MAP_F32  },
    { "ductTempMin",        offsetof(DeviceFacade, ductTempMin),        MAP_F32  },
    { "ductTempMax",        offsetof(DeviceFacade, ductTempMax),        MAP_F32  },
    { "ductRhMax",          offsetof(DeviceFacade, ductRhMax),          MAP_F32  },
    { "setPointTimeHigh",   offsetof(DeviceFacade, setPointTimeHigh),   MAP_U16  },
    { "setPointTimeLow",    offsetof(DeviceFacade, setPointTimeLow),    MAP_U16  },
    { "processEstimatedDuration", offsetof(DeviceFacade, processEstimatedDuration), MAP_U32 },
    { "processMinDuration", offsetof(DeviceFacade, processMinDuration), MAP_U32  },
    { "processRemainingDuration", offsetof(DeviceFacade, processRemainingDuration), MAP_U32 },
    { "estimatedRuntime",   offsetof(DeviceFacade, estimatedRuntime),   MAP_U32  },
    { "minRuntime",         offsetof(DeviceFacade, minRuntime),         MAP_U32  },
    { "estimatedBreakDuration", offsetof(DeviceFacade, estimatedBreakDuration), MAP_U32 },
    { "minBreakDuration",   offsetof(DeviceFacade, minBreakDuration),   MAP_U32  },
};

#define MAPPINGS_COUNT ((size_t)(sizeof(s_mappings) / sizeof(s_mappings[0])))

/* -----------------------------------------------------------------------
 * Apply — map one pre-split key/value token onto the DeviceFacade.
 * ----------------------------------------------------------------------- */
void JsonToParametersMapper_Apply(const char *key, const char *value,
                                  DeviceFacade *dev) {
    size_t i;
    if (!key || !key[0] || !value || !dev) { return; }

    for (i = 0U; i < MAPPINGS_COUNT; i++) {
        if (strcmp(key, s_mappings[i].key) != 0) { continue; }

        /* MISRA C:2012 Rule 11.3 deviation: descriptor-table field write. */
        void *fptr = (void *)(((uint8_t *)dev) + s_mappings[i].offset);

        char *end;
        errno = 0;
        switch (s_mappings[i].type) {
            case MAP_F32: {
                float v = strtof(value, &end);
                if (end != value && *end == '\0' && errno == 0 && isfinite(v)) { *(float *)fptr = v; }
                break;
            }
            case MAP_U16:
            case MAP_U32: {
                unsigned long v = strtoul(value, &end, 10);
                if (value[0] == '-' || end == value || *end != '\0' || errno != 0) { break; }
                if (s_mappings[i].type == MAP_U16 && v <= UINT16_MAX) { *(uint16_t *)fptr = (uint16_t)v; }
                if (s_mappings[i].type == MAP_U32 && v <= UINT32_MAX) { *(uint32_t *)fptr = (uint32_t)v; }
                break;
            }
            case MAP_BOOL:
                if (strcmp(value, "true") == 0) { *(bool *)fptr = true; }
                else if (strcmp(value, "false") == 0) { *(bool *)fptr = false; }
                break;
        }
        return; /* Key matched — no need to continue */
    }
    /* Unknown key: silently ignored (non-blocking, as per ST specification). */
}
/* Validate the entire object first. Unknown envelope/nested keys do not
 * become writes to matching keys inside their values. */
void JsonToParametersMapper_ParseAndApply(const char *json, int json_len,
                                          DeviceFacade *dev) {
    if (!json || !dev || json_len < 0) { return; }
    size_t len = json_len > 0 ? (size_t)json_len : strlen(json);
    if (!JsonFields_Valid(json, len)) { return; }
    for (size_t i = 0U; i < MAPPINGS_COUNT; ++i) {
        const char *value;
        size_t size;
        char token[64];
        if (!JsonFields_Find(json, len, s_mappings[i].key, &value, &size) || size >= sizeof(token)) { continue; }
        memcpy(token, value, size);
        token[size] = '\0';
        JsonToParametersMapper_Apply(s_mappings[i].key, token, dev);
    }
}

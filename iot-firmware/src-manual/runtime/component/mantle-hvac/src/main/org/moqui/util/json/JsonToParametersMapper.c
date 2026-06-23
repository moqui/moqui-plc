#include "JsonToParametersMapper.h"
#include "MoquiConf.h"
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdlib.h>

/*
 * MISRA C:2012 Rule 11.3 deviation: pointer casts via (uint8_t *) + offsetof
 * are required for descriptor-table-driven field writes.
 * All casts are to the exact declared type of each field.
 */

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
    { "airMixingEnabled",   offsetof(DeviceFacade, airMixingEnabled),   MAP_BOOL },
    { "airDistributionEnabled", offsetof(DeviceFacade, airDistributionEnabled), MAP_BOOL },
    { "rhControlEnabled",   offsetof(DeviceFacade, rhControlEnabled),   MAP_BOOL },
    { "rhControlOnly",      offsetof(DeviceFacade, rhControlOnly),      MAP_BOOL },
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

        switch (s_mappings[i].type) {
            case MAP_F32:
                *(float *)fptr = strtof(value, NULL);
                break;
            case MAP_U16:
                *(uint16_t *)fptr = (uint16_t)strtoul(value, NULL, 10);
                break;
            case MAP_U32:
                *(uint32_t *)fptr = (uint32_t)strtoul(value, NULL, 10);
                break;
            case MAP_BOOL:
                *(bool *)fptr = (strncmp(value, "true", 4) == 0);
                break;
            default:
                break;
        }
        return; /* Key matched — no need to continue */
    }
    /* Unknown key: silently ignored (non-blocking, as per ST specification). */
}

/*
 * 6-DOF robot arm trajectory mapping (moqui-device export#Trajectory)
 *
 * JSON payload shape (MQTT topic e.g. moqui/robot/arm1/trajectory):
 *   { "approximatedFunctionId": "100051", "waypointCount": 10,
 *     "axes": { "J1": [θ0,θ1,...,θ9], "J2": [...], ..., "J6": [...] } }
 *
 * The "axes" value is a nested object; each axis value is a float array.
 * ParseAndApply() below handles FLAT objects only and cannot parse this.
 * A dedicated JsonToParametersMapper_ParseAndApply_Trajectory() would be needed
 * that detects the opening '[' after "J1":"J6" keys and iterates the array,
 * e.g.:
 *
 *   if (strcmp(key, "J1") == 0 && value[0] == '[') {
 *       size_t idx = 0;
 *       const char *p = value + 1;
 *       while (*p && *p != ']' && idx < TRAJECTORY_POINT_LIST_MAX_SIZE) {
 *           dev->trajectory.points[idx].pos.x = strtof(p, (char **)&p);
 *           while (*p == ',' || *p == ' ') p++;
 *           idx++;
 *       }
 *       dev->trajectory.pointCount = (int32_t)idx;
 *   }
 *   // J2→pos.y, J3→pos.z, J4→pos.a, J5→pos.b, J6→pos.c
 *
 * The MapDesc descriptor table (s_mappings[]) applies to scalar fields only
 * and is not extended for array types.
 */

/* -----------------------------------------------------------------------
 * Minimal JSON scanner — flat object {"k":v, "k":v, ...}
 * Handles: numeric scalars, booleans (true/false), quoted strings.
 * Does NOT handle nested objects or arrays.
 * ----------------------------------------------------------------------- */
void JsonToParametersMapper_ParseAndApply(const char *json, int json_len,
                                          DeviceFacade *dev) {
    const char *p;
    const char *end;
    char key_buf[64];
    char val_buf[64];
    size_t klen;
    size_t vlen;
    const char *ks;
    const char *ke;
    const char *vs;
    const char *ve;

    if (!json || !dev) { return; }
    if (json_len <= 0) { json_len = (int)strlen(json); }

    p   = json;
    end = json + json_len;

    while (p < end) {
        /* Find the opening '"' of the next key */
        while (p < end && *p != '"') { p++; }
        if (p >= end) { break; }
        ks = p + 1;

        /* Find the closing '"' of the key */
        p = ks;
        while (p < end && *p != '"') { p++; }
        if (p >= end) { break; }
        ke = p;
        p++; /* skip closing '"' */

        /* Skip ':' and optional whitespace */
        while (p < end && (*p == ':' || *p == ' ')) { p++; }
        if (p >= end) { break; }

        /* Parse value: quoted string, boolean, or numeric */
        if (*p == '"') {
            vs = p + 1;
            p  = vs;
            while (p < end && *p != '"') { p++; }
            ve = p;
            if (p < end) { p++; }
        } else {
            vs = p;
            while (p < end && *p != ',' && *p != '}' && *p != ' ') { p++; }
            ve = p;
        }

        /* Copy key and value to null-terminated buffers, then dispatch */
        klen = (size_t)(ke - ks);
        vlen = (size_t)(ve - vs);
        if (klen == 0U || klen >= sizeof(key_buf)) { continue; }
        if (vlen >= sizeof(val_buf)) { vlen = sizeof(val_buf) - 1U; }

        memcpy(key_buf, ks, klen); key_buf[klen] = '\0';
        memcpy(val_buf, vs, vlen); val_buf[vlen] = '\0';

        JsonToParametersMapper_Apply(key_buf, val_buf, dev);
    }
}

#include "DeviceConfigLoader.h"
#include "LoggerFacade.h"
#include <string.h>
#include <stdlib.h>
#include <stdio.h>

static LoggerFacade s_log = { .enable = true, .loggerName = "DeviceConfigLoader" };

/* Recipe files are embedded in flash at link time via EMBED_TXTFILES in CMakeLists.txt. */
extern const char _binary_Phase1HvacCooling_HvacDeviceConfig_json_start[];
extern const char _binary_Phase1HvacCooling_HvacDeviceConfig_json_end[];
extern const char _binary_Phase2HvacDrying_HvacDeviceConfig_json_start[];
extern const char _binary_Phase2HvacDrying_HvacDeviceConfig_json_end[];
extern const char _binary_Phase3HvacHeating_HvacDeviceConfig_json_start[];
extern const char _binary_Phase3HvacHeating_HvacDeviceConfig_json_end[];
extern const char _binary_Phase4HvacDrying_Progressive_HvacDeviceConfig_json_start[];
extern const char _binary_Phase4HvacDrying_Progressive_HvacDeviceConfig_json_end[];
extern const char _binary_Phase5HvacDrying_Intensive_HvacDeviceConfig_json_start[];
extern const char _binary_Phase5HvacDrying_Intensive_HvacDeviceConfig_json_end[];
extern const char _binary_TestRecipes_json_start[];
extern const char _binary_TestRecipes_json_end[];

typedef struct {
    const char *name;
    const char *json_start;
    const char *json_end;
} RecipeEntry;

static const RecipeEntry s_registry[] = {
    { "Phase1HvacCooling",
      _binary_Phase1HvacCooling_HvacDeviceConfig_json_start,
      _binary_Phase1HvacCooling_HvacDeviceConfig_json_end },
    { "Phase2HvacDrying",
      _binary_Phase2HvacDrying_HvacDeviceConfig_json_start,
      _binary_Phase2HvacDrying_HvacDeviceConfig_json_end },
    { "Phase3HvacHeating",
      _binary_Phase3HvacHeating_HvacDeviceConfig_json_start,
      _binary_Phase3HvacHeating_HvacDeviceConfig_json_end },
    { "Phase4HvacDrying_Progressive",
      _binary_Phase4HvacDrying_Progressive_HvacDeviceConfig_json_start,
      _binary_Phase4HvacDrying_Progressive_HvacDeviceConfig_json_end },
    { "Phase5HvacDrying_Intensive",
      _binary_Phase5HvacDrying_Intensive_HvacDeviceConfig_json_start,
      _binary_Phase5HvacDrying_Intensive_HvacDeviceConfig_json_end },
    { "TestRecipes",
      _binary_TestRecipes_json_start,
      _binary_TestRecipes_json_end },
};

#define REGISTRY_SIZE (sizeof(s_registry) / sizeof(s_registry[0]))

/*
 * Minimal JSON scanner — works on flat and one-level-nested objects with numeric,
 * boolean, and string scalar values. Handles our recipe format exactly.
 * Not a general-purpose parser; does not handle strings containing '{', '}', or ':'.
 */

static const char *scan_key(const char *json, const char *key, size_t json_len) {
    /* Build '"key":' pattern */
    char pat[72];
    int pat_len = snprintf(pat, sizeof(pat), "\"%s\"", key);
    if (pat_len <= 0 || pat_len >= (int)sizeof(pat)) return NULL;

    const char *end = json + json_len;
    const char *p = json;
    while (p < end) {
        const char *found = (const char *)memmem(p, (size_t)(end - p), pat, (size_t)pat_len);
        if (!found) return NULL;
        /* Skip to value — past optional whitespace and ':' */
        const char *v = found + pat_len;
        while (v < end && (*v == ' ' || *v == '\t' || *v == '\n' || *v == '\r')) v++;
        if (v >= end || *v != ':') { p = found + 1; continue; }
        v++;
        while (v < end && (*v == ' ' || *v == '\t' || *v == '\n' || *v == '\r')) v++;
        return v; /* points to first char of value */
    }
    return NULL;
}

static float get_float(const char *json, size_t json_len, const char *key, float def) {
    const char *v = scan_key(json, key, json_len);
    if (!v) return def;
    return strtof(v, NULL);
}

static uint32_t get_u32(const char *json, size_t json_len, const char *key, uint32_t def) {
    const char *v = scan_key(json, key, json_len);
    if (!v) return def;
    return (uint32_t)strtoul(v, NULL, 10);
}

static uint16_t get_u16(const char *json, size_t json_len, const char *key, uint16_t def) {
    return (uint16_t)get_u32(json, json_len, key, def);
}

static bool get_bool(const char *json, size_t json_len, const char *key, bool def) {
    const char *v = scan_key(json, key, json_len);
    if (!v) return def;
    if (strncmp(v, "true", 4) == 0)  return true;
    if (strncmp(v, "false", 5) == 0) return false;
    return def;
}

/* Extract the substring bounded by the '{' '}' of the given key's nested object. */
static bool get_object(const char *json, size_t json_len,
                       const char *key, const char **obj_start, size_t *obj_len) {
    const char *v = scan_key(json, key, json_len);
    if (!v || *v != '{') return false;
    v++; /* skip '{' */
    int depth = 1;
    const char *p = v;
    const char *end = json + json_len;
    while (p < end && depth > 0) {
        if (*p == '{') depth++;
        else if (*p == '}') depth--;
        p++;
    }
    if (depth != 0) return false;
    *obj_start = v;
    *obj_len   = (size_t)(p - 1 - v);
    return true;
}

static void load_actuator(const char *json, size_t json_len, const char *key, Actuator *act) {
    const char *obj; size_t len;
    if (!get_object(json, json_len, key, &obj, &len)) return;
    act->enableTime        = get_u16(obj, len, "enableTime",        act->enableTime);
    act->disableTime       = get_u16(obj, len, "disableTime",       act->disableTime);
    act->diagnosticsEnable = get_bool(obj, len, "diagnosticsEnable",act->diagnosticsEnable);
}

static void load_pid(const char *json, size_t json_len, const char *key, ProcessPid *pid) {
    const char *obj; size_t len;
    if (!get_object(json, json_len, key, &obj, &len)) return;
    pid->gain            = get_float(obj, len, "gain",            pid->gain);
    pid->integrationTime = get_float(obj, len, "integrationTime", pid->integrationTime);
    pid->derivationTime  = get_float(obj, len, "derivationTime",  pid->derivationTime);
    pid->outputMin       = get_float(obj, len, "outputMin",       pid->outputMin);
    pid->outputMax       = get_float(obj, len, "outputMax",       pid->outputMax);
}

bool DeviceConfigLoader_Load(const char *recipeName, DeviceFacade *dev) {
    if (!recipeName || !dev) return false;

    const RecipeEntry *entry = NULL;
    for (size_t i = 0; i < REGISTRY_SIZE; i++) {
        if (strcmp(s_registry[i].name, recipeName) == 0) {
            entry = &s_registry[i];
            break;
        }
    }
    if (!entry) {
        LOGGER_LOG(&s_log, LOG_LEVEL_ERROR, "Unknown recipe: %s", recipeName);
        return false;
    }

    const char *json = entry->json_start;
    size_t jlen = (size_t)(entry->json_end - entry->json_start);

    /* Temperature / RH setpoints and limits */
    dev->tempSetpoint          = get_float(json, jlen, "tempSetpoint",          dev->tempSetpoint);
    dev->tempHysteresis        = get_float(json, jlen, "tempHysteresis",        dev->tempHysteresis);
    dev->tempMin               = get_float(json, jlen, "tempMin",               dev->tempMin);
    dev->tempMax               = get_float(json, jlen, "tempMax",               dev->tempMax);
    dev->rhSetpoint            = get_float(json, jlen, "rhSetpoint",            dev->rhSetpoint);
    dev->rhHysteresis          = get_float(json, jlen, "rhHysteresis",          dev->rhHysteresis);
    dev->rhMin                 = get_float(json, jlen, "rhMin",                 dev->rhMin);
    dev->rhMax                 = get_float(json, jlen, "rhMax",                 dev->rhMax);
    dev->ductTempMin           = get_float(json, jlen, "ductTempMin",           dev->ductTempMin);
    dev->ductTempMax           = get_float(json, jlen, "ductTempMax",           dev->ductTempMax);
    dev->ductRhMax             = get_float(json, jlen, "ductRhMax",             dev->ductRhMax);

    /* Boolean control flags */
    dev->rhControlEnabled        = get_bool(json, jlen, "rhControlEnabled",        dev->rhControlEnabled);
    dev->rhControlOnly           = get_bool(json, jlen, "rhControlOnly",           dev->rhControlOnly);
    dev->airMixingEnabled        = get_bool(json, jlen, "airMixingEnabled",        dev->airMixingEnabled);
    dev->airDistributionEnabled  = get_bool(json, jlen, "airDistributionEnabled",  dev->airDistributionEnabled);
    dev->setPointTimeHigh        = get_u16(json,  jlen, "setPointTimeHigh",        dev->setPointTimeHigh);
    dev->setPointTimeLow         = get_u16(json,  jlen, "setPointTimeLow",         dev->setPointTimeLow);

    /* Process timing (seconds) */
    dev->estimatedRuntime        = get_u32(json, jlen, "estimatedRuntime",        dev->estimatedRuntime);
    dev->minRuntime              = get_u32(json, jlen, "minRuntime",              dev->minRuntime);
    dev->estimatedBreakDuration  = get_u32(json, jlen, "estimatedBreakDuration",  dev->estimatedBreakDuration);
    dev->minBreakDuration        = get_u32(json, jlen, "minBreakDuration",        dev->minBreakDuration);
    dev->processEstimatedDuration= get_u32(json, jlen, "processEstimatedDuration",dev->processEstimatedDuration);
    dev->processMinDuration      = get_u32(json, jlen, "processMinDuration",      dev->processMinDuration);

    /* Actuator config (timing only — IDs/names are set by application code) */
    load_actuator(json, jlen, "coldGlycolPump", &dev->coldGlycolPump);
    load_actuator(json, jlen, "hotGlycolPump",  &dev->hotGlycolPump);
    load_actuator(json, jlen, "airFlow",        &dev->airFlow);
    load_actuator(json, jlen, "highFlowDamper", &dev->highFlowDamper);
    load_actuator(json, jlen, "lowFlowDamper",  &dev->lowFlowDamper);
    dev->airFlowRef = get_float(json, jlen, "airFlowRef", dev->airFlowRef);

    /* PID config */
    load_pid(json, jlen, "coldGlycolValve", &dev->coldGlycolValve);
    load_pid(json, jlen, "hotGlycolValve",  &dev->hotGlycolValve);
    load_pid(json, jlen, "ahuFan",          &dev->ahuFan);
    dev->ahuFanSpeedSetpoint = get_float(json, jlen, "ahuFanSpeedSetpoint", dev->ahuFanSpeedSetpoint);

    LOGGER_LOG(&s_log, LOG_LEVEL_INFO, "Loaded recipe: %s", recipeName);
    return true;
}

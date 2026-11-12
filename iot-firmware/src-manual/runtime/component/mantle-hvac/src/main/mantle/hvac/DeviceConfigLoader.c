#include "DeviceConfigLoader.h"
#include "LoggerFacade.h"
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <errno.h>
#include <math.h>
#include "JsonFields.h"

static LoggerFacade s_log = { .enable = true, .loggerName = MOQUI_APPLICATION_DEVICE_ID };

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

/* All lookups are top-level within a validated object and bounded by len. */
static bool token(const char *json, size_t len, const char *key, char out[64]) {
    const char *v;
    size_t n;
    if (!JsonFields_Find(json, len, key, &v, &n) || n >= 64U) { return false; }
    memcpy(out, v, n);
    out[n] = '\0';
    return true;
}
static float get_float(const char *json, size_t len, const char *key, float def) {
    char text[64], *end;
    if (!token(json, len, key, text)) { return def; }
    errno = 0;
    float v = strtof(text, &end);
    return end != text && *end == '\0' && errno == 0 && isfinite(v) ? v : def;
}
static uint32_t get_u32(const char *json, size_t len, const char *key, uint32_t def) {
    char text[64], *end;
    if (!token(json, len, key, text) || text[0] == '-') { return def; }
    errno = 0;
    unsigned long v = strtoul(text, &end, 10);
    return end != text && *end == '\0' && errno == 0 && v <= UINT32_MAX ? (uint32_t)v : def;
}
static uint16_t get_u16(const char *json, size_t len, const char *key, uint16_t def) {
    uint32_t v = get_u32(json, len, key, def);
    return v <= UINT16_MAX ? (uint16_t)v : def;
}
static bool get_bool(const char *json, size_t len, const char *key, bool def) {
    char text[64];
    if (!token(json, len, key, text)) { return def; }
    if (strcmp(text, "true") == 0) { return true; }
    if (strcmp(text, "false") == 0) { return false; }
    return def;
}
static bool get_object(const char *json, size_t len, const char *key,
                       const char **obj, size_t *obj_len) {
    return JsonFields_Find(json, len, key, obj, obj_len) && **obj == '{';
}
static void get_identity(const char *json, size_t len, const char *key,
                         char storage[64], const char **target) {
    const char *v;
    size_t n;
    if (JsonFields_Find(json, len, key, &v, &n) && n >= 2U &&
        v[0] == '"' && n - 2U < 64U && memchr(v + 1, '\\', n - 2U) == NULL) {
        memcpy(storage, v + 1, n - 2U);
        storage[n - 2U] = '\0';
        *target = storage;
    }
}

static void load_actuator(const char *json, size_t json_len, const char *key, Actuator *act) {
    const char *obj; size_t len;
    if (!get_object(json, json_len, key, &obj, &len)) return;
    get_identity(obj, len, "actuatorId", act->actuatorIdStorage, &act->actuatorId);
    get_identity(obj, len, "actuatorName", act->actuatorNameStorage, &act->actuatorName);
    act->actuationType = (ActuatorActuationType)get_u16(obj, len, "actuationType", act->actuationType);
    act->feedbackType = (ActuatorFeedbackType)get_u16(obj, len, "feedbackType", act->feedbackType);
    act->model = (ActuatorModel)get_u16(obj, len, "model", act->model);
    act->enableTime        = get_u16(obj, len, "enableTime",        act->enableTime);
    act->disableTime       = get_u16(obj, len, "disableTime",       act->disableTime);
    act->diagnosticsEnable = get_bool(obj, len, "diagnosticsEnable",act->diagnosticsEnable);
}

static void load_pid(const char *json, size_t json_len, const char *key, ProcessPid *pid) {
    const char *obj; size_t len;
    if (!get_object(json, json_len, key, &obj, &len)) return;
    get_identity(obj, len, "controlSystemId", pid->controlSystemIdStorage, &pid->controlSystemId);
    get_identity(obj, len, "controlSystemName", pid->controlSystemNameStorage, &pid->controlSystemName);
    pid->feedbackMultiplier = get_float(obj, len, "feedbackMultiplier", 1.0f);
    pid->setpointMultiplier = get_float(obj, len, "setpointMultiplier", 1.0f);
    pid->setpointMin = get_float(obj, len, "setpointMin", pid->setpointMin);
    pid->setpointMax = get_float(obj, len, "setpointMax", pid->setpointMax);
    pid->atSetpointHysteresis = get_float(obj, len, "atSetpointHysteresis", pid->atSetpointHysteresis);
    pid->tickTimeMs = get_u32(obj, len, "tickTimeMs", 100U);
    pid->setpointEpsilon = get_float(obj, len, "setpointEpsilon", 0.000001f);
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

    if (jlen > 0U && json[jlen - 1U] == '\0') { --jlen; }
    if (!JsonFields_Valid(json, jlen)) { return false; }

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

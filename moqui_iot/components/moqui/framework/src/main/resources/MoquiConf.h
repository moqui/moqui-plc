#ifndef MOQUI_CONF_H
#define MOQUI_CONF_H

/*
 * MoquiConf — centralized structural constants.
 *
 * Faithful port of MoquiConf.st (VAR_GLOBAL CONSTANT).
 * Only structural sizing and protocol constants live here.
 * MQTT runtime values (broker URI, topic prefix, stack sizes) remain in Kconfig.
 */

/* ========== Framework ========== */
#define MOQUI_RETRY_ON_ERROR       (1U)
#define MOQUI_MIN_RETRY_TIME       (10U)   /* ST: minRetryTime = 10 s */
#define MOQUI_MAX_RETRY_COUNT      (5U)    /* ST: maxRetryCount = 5 */

/* ========== Logger ========== */
#define LOG_MAX_SIZE               (100U)
#define LOG_SOURCE_LIST_MAX_SIZE   (50U)
#define LOG_JSON_PAYLOAD_MAX_SIZE  (32768U)
#define JSON_PAYLOAD_MAX_SIZE      (8192U)
#define JSON_ELEMENT_LIST_MAX_SIZE (100U)
#define LOG_APPENDER_BATCH_SIZE    (10U)
#define LOG_APPENDER_TIMEOUT_US    (50000U)

/* ========== MQTT topics (structural names, not runtime addresses) ========== */
#define MOQUI_LOG_TOPIC            "moqui-log"
#define MOQUI_LIVE_PARAMS_SUB_TOPIC "liveParamsSub"
#define MOQUI_LIVE_PARAMS_PUB_TOPIC "liveParamsPub"

/* ========== Communication Protocols ========== */
#define MODBUS_OVERRANGE           (27649U)
#define MODBUS_OVERFLOW            (32512U)

/* ========== Signal Management ========== */
#define SIGNAL_LIST_MAX_SIZE       (200U)

/* ========== Device Config Management ========== */
#define DEVICE_CONFIG_LIST_MAX_SIZE   (100U)
#define MOQUI_DEFAULT_CONFIG_TYPE     "HvacDeviceConfig"
#define MOQUI_DEVICE_CONFIG_STORAGE_PATH ""

/* ========== Device ========== */
#define ACTUATOR_GROUP_MAX_SIZE    (8U)

/* ========== PID ========== */
/* MISRA C:2012 Rule 7.4 — named constant replaces magic float 1.0e6f */
#define PID_INTEGRAL_SAT_LIMIT     (1.0e6f)

/* ========== Status Manager error IDs ========== */
#define STATUS_MGR_ERROR_EXTERNAL  (1U)   /* Error from activationCondition */
#define STATUS_MGR_ERROR_TIMEOUT   (2U)   /* Total timeout expired */

#endif /* MOQUI_CONF_H */

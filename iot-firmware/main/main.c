#include <stdio.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#include "platform.h"
#include "Main.h"
#include "MoquiStart.h"
#include "MqttClient.h"
#include "MqttLogAppender.h"
#include "MqttParameterSub.h"
#include "MqttParameterPub.h"
#include "LoggerFacade.h"
#include "DeviceConfigLoader.h"
#include "HvacDeviceConfigOps.h"
#include "ParametersToJsonMapper.h"
#include "JsonToParametersMapper.h"
#include "MoquiConf.h"
#include "ec.h"
#include "sdkconfig.h"

#ifdef CONFIG_MOQUI_ENABLE_TEST_SUITE
#include "HvacTestSuite.h"
#endif

/*
 * Task layout — mirrors the IEC 61131-3 task model:
 *
 *   Control_Task  Core 1  MAX priority    100 ms  ≈ StartTask P1
 *   IotSlow_Task  Core 1  MAX-2 priority  1000 ms ≈ MqttParameterSubTask P1
 *                                                    LogDispatcherTask P3
 *                                                    MqttParameterPubTask P3 (every 3 cycles)
 *   IoT_Task      Core 0  priority 5      event   MQTT I/O queue (PAL layer)
 *
 * IotSlow_Task is pinned to Core 1 alongside Control_Task.  Control_Task blocks
 * ~90 ms per 100 ms cycle in vTaskDelayUntil, giving IotSlow_Task ample runtime
 * without requiring any mutex on s_hvac (single-core access from core 1 tasks).
 *
 * NOTE: MqttParameterSub rx_callback is invoked by the ESP-IDF MQTT event task
 * on Core 0 and writes to s_hvac.  A production build should protect s_hvac with
 * a FreeRTOS mutex; for the current scope the callback rate is low (user-triggered)
 * and the risk of a torn read is accepted.
 */

#define CONTROL_TASK_STACK_SIZE   8192
#define IOT_SLOW_TASK_STACK_SIZE  4096
#define IOT_TASK_STACK_SIZE       4096

/* Control_Task (Core 1, highest priority) */
static StaticTask_t xControlTaskBuffer;
static StackType_t  xControlStack[CONTROL_TASK_STACK_SIZE];

/* IotSlow_Task (Core 1, below control) */
static StaticTask_t xIotSlowTaskBuffer;
static StackType_t  xIotSlowStack[IOT_SLOW_TASK_STACK_SIZE];

/* IoT_Task (Core 0, MQTT I/O) */
static StaticTask_t xIotTaskBuffer;
static StackType_t  xIotStack[IOT_TASK_STACK_SIZE];

/* Shared application state — all written from Core 1 tasks only (see note above). */
static MoquiStart       s_start;
static DeviceFacade     s_hvac;
static DeviceConfigOps  s_hvac_ops;
static MqttLogAppender  s_log_appender;
static LogEvent         s_log_drain[LOG_APPENDER_BATCH_SIZE];
static MqttParameterSub s_param_sub;
static MqttParameterPub s_param_pub;

/* -------------------------------------------------------------------------
 * Control_Task  (~StartTask P1 in IEC)
 *
 * Hard real-time loop: config lifecycle, I/O scan, rule engine.
 * Log drain is kept here (same task as LoggerFacade_Log writes) to avoid
 * cross-core races on the ring buffer without a mutex.
 * ------------------------------------------------------------------------- */
#ifdef CONFIG_MOQUI_ENABLE_TEST_SUITE
static void __attribute__((unused)) hvac_production_task(void *pvParameters) {
#else
static void hvac_production_task(void *pvParameters) {
#endif
    Clocks   clks = {0};
    uint32_t tick = 0U;
    uint16_t n_log_events;

    HvacDeviceConfigOps_Init(&s_hvac_ops, &s_hvac);
    s_start.configMgmt.configCmds.configOps              = &s_hvac_ops;
    s_start.configMgmt.configCmds.defaultConfigType       = "HvacDeviceConfig";
    s_start.configMgmt.configCmds.deviceConfigStoragePath = "";

    /* Wire I/O hooks (application provides the actual GPIO/ADC/I2C mapping) */
    /* s_start.inputProcessing.readInputs    = hvac_read_inputs;   */
    /* s_start.inputProcessing.device_facade = &s_hvac;            */
    /* s_start.outputProcessing.writeOutputs = hvac_write_outputs; */
    /* s_start.outputProcessing.device_facade = &s_hvac;           */

    s_start.init   = true;
    s_start.enable = true;

    TickType_t xLastWake = xTaskGetTickCount();
    const TickType_t xPeriod = pdMS_TO_TICKS(100U);

    while (1) {
        vTaskDelayUntil(&xLastWake, xPeriod);
        tick++;

        clks.clock10ms    = true;
        clks.clock100ms   = true;
        clks.clock1s      = (tick %  10U) == 0U;
        clks.clock1minute = (tick % 600U) == 0U;

        MoquiStart_Update(&s_start, &clks);

        bool done  = false;
        bool error = false;
        Main_Update(&s_hvac, &clks,
                    s_start.operationType,
                    s_start.enable,
                    s_start.deviceConfigContextResetRequest,
                    &done, &error);
        s_start.mainDone = done;

        /* Drain log ring buffer -> MqttLogAppender (same task as writer — no race). */
        LoggerFacade_DrainBuffer(s_log_drain, LOG_APPENDER_BATCH_SIZE, &n_log_events);
        s_log_appender.logBuffer     = s_log_drain;
        s_log_appender.logBufferSize = n_log_events;
        s_log_appender.execute       = (n_log_events > 0U);
        MqttLogAppender_Update(&s_log_appender);

        clks.clock10ms  = false;
        clks.clock100ms = false;
    }
}

/* -------------------------------------------------------------------------
 * IotSlow_Task  (~MqttParameterSubTask P1 + LogDispatcherTask P3 +
 *                 MqttParameterPubTask P3 in IEC)
 *
 * Runs on Core 1 at priority MAX-2, below Control_Task.  Wakes every 1 s.
 * Pinned to Core 1 so s_hvac is accessed from a single core (no mutex needed).
 * ------------------------------------------------------------------------- */
#ifndef CONFIG_MOQUI_ENABLE_TEST_SUITE
static void iot_slow_task(void *pvParameters) {
    uint32_t cycle = 0U;
    const TickType_t xPeriod = pdMS_TO_TICKS(1000U);
    TickType_t xLastWake = xTaskGetTickCount();

    /* Wire pub/sub to the HVAC device facade (dependency injection). */
    s_param_sub.device  = &s_hvac;
    s_param_sub.parseFn = (ParamParseFn)JsonToParametersMapper_ParseAndApply;

    s_param_pub.device      = &s_hvac;
    s_param_pub.serializeFn = (ParamSerializeFn)serialize_device_facade;

    while (1) {
        vTaskDelayUntil(&xLastWake, xPeriod);
        cycle++;

        bool connected = pal_mqtt_is_connected();

        /* ~MqttParameterSubTask P1 (1 s): subscription management + live param rx */
        MqttParameterSub_Update(&s_param_sub, connected);

        /* Per-actuator state plus optional peer-PLC parameter replication. */
        if ((cycle % 3U) == 0U) {
            MqttClient_PublishActuatorState(&s_hvac.coldGlycolPump);
            MqttClient_PublishActuatorState(&s_hvac.hotGlycolPump);
            MqttClient_PublishActuatorState(&s_hvac.airFlow);
            MqttParameterPub_Update(&s_param_pub, connected && ec.paramsPubEnable);
        }
    }
}
#endif /* CONFIG_MOQUI_ENABLE_TEST_SUITE */

/* -------------------------------------------------------------------------
 * control_task  (test build only — replaces hvac_production_task)
 * ------------------------------------------------------------------------- */
#ifdef CONFIG_MOQUI_ENABLE_TEST_SUITE
static HvacTestSuite s_test_suite;

static void control_task(void *pvParameters) {
    printf("[I] Control Task (HvacTestSuite) started on core %d\n", xPortGetCoreID());

    TickType_t xLastWakeTime = xTaskGetTickCount();
    const TickType_t xFrequency = pdMS_TO_TICKS(20U);
    uint32_t cycle_count = 0U;

    while (1) {
        vTaskDelayUntil(&xLastWakeTime, xFrequency);
        cycle_count++;
        s_test_suite.clks.clock1s = (cycle_count % 50U) == 0U;

        HvacTestSuite_Update(&s_test_suite);

        if (s_test_suite.testFailed) {
            printf("[E] HVAC Test Suite FAILED at step %d\n", s_test_suite.failStep);
            vTaskDelay(portMAX_DELAY);
        } else if (s_test_suite.testDone) {
            if ((cycle_count % 250U) == 0U) {
                printf("[I] Test suite finished successfully. System Idle.\n");
            }
        }
    }
}
#endif /* CONFIG_MOQUI_ENABLE_TEST_SUITE */

/* -------------------------------------------------------------------------
 * app_main — ESP32 entry point
 * ------------------------------------------------------------------------- */
void app_main(void) {
    printf("[I] Moqui IoT Firmware Initializing...\n");

    pal_hardware_init();
    MqttClient_Init(NULL);

    /* IoT_Task — Core 0, priority 5: MQTT I/O queue (PAL layer) */
    xTaskCreateStaticPinnedToCore(
        MqttClient_Task, "IoT_Task",
        IOT_TASK_STACK_SIZE, NULL, 5,
        xIotStack, &xIotTaskBuffer, 0);

#ifdef CONFIG_MOQUI_ENABLE_TEST_SUITE
    /* Test build: single control task, no slow IoT task. */
    xTaskCreateStaticPinnedToCore(
        control_task, "Control_Task",
        CONTROL_TASK_STACK_SIZE, NULL, configMAX_PRIORITIES - 1,
        xControlStack, &xControlTaskBuffer, 1);
#else
    /* Production build: control + slow IoT tasks, both on Core 1. */
    xTaskCreateStaticPinnedToCore(
        hvac_production_task, "Control_Task",
        CONTROL_TASK_STACK_SIZE, NULL, configMAX_PRIORITIES - 1,
        xControlStack, &xControlTaskBuffer, 1);

    xTaskCreateStaticPinnedToCore(
        iot_slow_task, "IotSlow_Task",
        IOT_SLOW_TASK_STACK_SIZE, NULL, configMAX_PRIORITIES - 2,
        xIotSlowStack, &xIotSlowTaskBuffer, 1);
#endif
}

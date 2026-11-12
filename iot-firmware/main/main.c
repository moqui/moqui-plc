#include <stdio.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "sdkconfig.h"
#include "platform.h"
#include "Main.h"
#include "MoquiStart.h"
#include "MqttClient.h"
#include "MqttLogAppender.h"
#include "MqttParameterSub.h"
#include "MqttParameterPub.h"
#include "LoggerFacade.h"
#include "HvacDeviceConfigOps.h"
#include "ParametersToJsonMapper.h"
#include "JsonToParametersMapper.h"
#include "ec.h"
#ifdef CONFIG_MOQUI_ENABLE_TEST_SUITE
#include "HvacTestSuite.h"
#endif

/* One task owns the application, config sequencer and logger ring. MQTT event
 * callbacks only enqueue bytes. The low-priority task owns network publishing. */
static StaticTask_t s_control_task, s_iot_task;
static StackType_t s_control_stack[CONFIG_MOQUI_CONTROL_TASK_STACK / sizeof(StackType_t)];
static StackType_t s_iot_stack[CONFIG_IOT_FIRMWARE_TASK_STACK / sizeof(StackType_t)];
#ifndef CONFIG_MOQUI_ENABLE_TEST_SUITE
static MoquiStart s_start;
static DeviceFacade s_hvac;
static DeviceConfigOps s_ops;
static MqttParameterSub s_sub;
static MqttParameterPub s_pub;
#endif
static MqttLogAppender s_appender;
static LogEvent s_drain[LOG_APPENDER_BATCH_SIZE];

static void drain_logs(void) {
    uint16_t count = 0U;
    LoggerFacade_DrainBuffer(s_drain, LOG_APPENDER_BATCH_SIZE, &count);
    s_appender.logBuffer = s_drain;
    s_appender.logBufferSize = count;
    s_appender.execute = count > 0U;
    MqttLogAppender_Update(&s_appender);
}

#ifndef CONFIG_MOQUI_ENABLE_TEST_SUITE
static void main_update(void *context, const Clocks *clks, OperatingMode mode,
                        bool enable, bool configReset, bool *done, bool *error) {
    Main_Update(context, clks, mode, enable, configReset, done, error);
}
static void apply_parameters(const char *payload, int len, void *context) {
    JsonToParametersMapper_ParseAndApply(payload, len, context);
}
static bool serialize_parameters(const void *context, char *out, size_t max) {
    return serialize_device_facade(context, out, max);
}

static void control_task(void *arg) {
    (void)arg;
    Clocks clks = {0};
    TickType_t wake = xTaskGetTickCount();
    const TickType_t period = pdMS_TO_TICKS(10U);
    configASSERT(period > 0U);
    uint32_t cycle = 0U;

    HvacDeviceConfigOps_Init(&s_ops, &s_hvac);
    s_start.configMgmt.configCmds.configOps = &s_ops;
    s_start.configMgmt.configCmds.defaultConfigType = MOQUI_DEFAULT_CONFIG_TYPE;
    s_start.configMgmt.configCmds.deviceConfigStoragePath = MOQUI_DEVICE_CONFIG_STORAGE_PATH;
    s_start.mainUpdate = main_update;
    s_start.mainContext = &s_hvac;
    s_start.init = true;
    s_start.enable = true;
    s_sub.device = &s_hvac;
    s_sub.parseFn = apply_parameters;
    s_pub.device = &s_hvac;
    s_pub.serializeFn = serialize_parameters;

    for (;;) {
        vTaskDelayUntil(&wake, period);
        /* Input commands are applied by this owner before the next scan. */
        bool connected = pal_mqtt_is_connected();
        MqttParameterSub_Update(&s_sub, connected && ec.paramsSubEnable);
        MoquiStart_Update(&s_start, &clks);
        if (++cycle == 300U) {
            cycle = 0U;
            MqttClient_PublishActuatorState(&s_hvac.coldGlycolPump);
            MqttClient_PublishActuatorState(&s_hvac.hotGlycolPump);
            MqttClient_PublishActuatorState(&s_hvac.airFlow);
            MqttParameterPub_Update(&s_pub, connected && ec.paramsPubEnable);
        }
        drain_logs();
    }
}
#else
static HvacTestSuite s_tests;
static void control_task(void *arg) {
    (void)arg;
    TickType_t wake = xTaskGetTickCount();
    uint32_t cycles = 0U;
    for (;;) {
        vTaskDelayUntil(&wake, pdMS_TO_TICKS(10U));
        s_tests.clks.clock10ms = true;
        s_tests.clks.clock100ms = (cycles % 10U) == 0U;
        s_tests.clks.clock1s = (++cycles % 100U) == 0U;
        HvacTestSuite_Update(&s_tests);
        drain_logs();
        if (s_tests.testFailed) {
            printf("HVAC test failed at step %u\n", (unsigned)s_tests.failStep);
            vTaskSuspend(NULL);
        }
    }
}
#endif

void app_main(void) {
    pal_hardware_init();
    MqttClient_Init(NULL);
    configASSERT(xTaskCreateStaticPinnedToCore(MqttClient_Task, "IoT_Task",
        sizeof(s_iot_stack), NULL, 5, s_iot_stack, &s_iot_task, 0) != NULL);
    configASSERT(xTaskCreateStaticPinnedToCore(control_task, "Control_Task",
        sizeof(s_control_stack), NULL, configMAX_PRIORITIES - 1,
        s_control_stack, &s_control_task, 1) != NULL);
}

#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
#include "ClockGeneration.h"
#include "MoquiStart.h"
#include "HvacTestSuite.h"
#include "HvacDeviceConfigOps.h"
#include "DeviceConfigLoader.h"
#include "JsonToParametersMapper.h"
#include "JsonFields.h"
#include "MqttParameterSub.h"
#include "MqttClient.h"
#include "Fieldbus_Analog.h"
#include "ParametersToJsonMapper.h"
#include "ParameterLogger.h"
#include "DeviceManager.h"

extern void host_receive(const char *, const char *);
extern bool host_connected;
extern unsigned host_subscribes;
static unsigned main_calls, init_calls, reset_calls, input_calls, output_calls;
static bool in_main;
static void input(void *dev) { (void)dev; assert(!in_main); ++input_calls; }
static void output(const void *dev) { (void)dev; assert(!in_main); ++output_calls; }
static void fake_main(void *ctx, const Clocks *clks, OperatingMode op,
                      bool enable, bool reset, bool *done, bool *error) {
    (void)ctx; (void)clks; assert(enable); in_main = true;
    assert(input_calls == output_calls + 1U);
    ++main_calls; init_calls += op == OPERATING_MODE_INIT; reset_calls += reset;
    *done = false; *error = false; in_main = false;
}
static uint32_t list(void *ctx, const char *path, const char *type,
                     char names[][64], uint16_t max, uint16_t *count) {
    (void)ctx; (void)path; (void)type; assert(max >= 2);
    strcpy(names[0], "A"); strcpy(names[1], "B"); *count = 2; return 0;
}
static unsigned loaded;
static uint32_t load(void *ctx, const char *path, const char *type, const char *name) {
    (void)ctx; (void)path; (void)type; assert(name[0] == (loaded ? 'B' : 'A')); ++loaded; return 0;
}
static void test_start(void) {
    DeviceConfigOps ops = {.listConfigs = list, .loadConfig = load};
    MoquiStart start = {.init = true, .enable = true, .mainUpdate = fake_main};
    Clocks clks = {0};
    start.inputProcessing.readInputs = input;
    start.inputProcessing.device_facade = &start;
    start.outputProcessing.writeOutputs = output;
    start.outputProcessing.device_facade = &start;
    start.configMgmt.configCmds.configOps = &ops;
    start.configMgmt.configCmds.defaultConfigType = "Test";
    for (unsigned i = 0; i < 12; ++i) { MoquiStart_Update(&start, &clks); }
    assert(loaded == 1 && init_calls == 1 && main_calls > 0);
    start.mainDone = true;
    for (unsigned i = 0; i < 6; ++i) { MoquiStart_Update(&start, &clks); }
    assert(loaded == 2 && init_calls == 1 && reset_calls == 1);
    start.mainDone = true;
    for (unsigned i = 0; i < 6; ++i) { MoquiStart_Update(&start, &clks); }
    assert(start.allConfigLoaded && !start.enable);
    unsigned calls = main_calls;
    MoquiStart_Update(&start, &clks); assert(main_calls == calls);
}
static void test_clocks(void) {
    ClockGeneration gen = {.operationType = OPERATING_MODE_INIT}; Clocks clks = {0};
    unsigned c100=0, c1=0, c60=0;
    for (unsigned i = 0; i < 6000; ++i) {
        ClockGeneration_Update(&gen, &clks); gen.operationType = OPERATING_MODE_RUN;
        c100 += clks.clock100ms; c1 += clks.clock1s; c60 += clks.clock1minute;
    }
    assert(c100 == 600 && c1 == 60 && c60 == 1);
}
static void test_recipes(void) {
    DeviceFacade dev = {0}; DeviceConfigOps ops;
    HvacDeviceConfigOps_Init(&ops, &dev);
    char names[8][64]; uint16_t count=0;
    assert(ops.listConfigs(ops.context, "", "HvacDeviceConfig", names, 8, &count) == 0 && count == 5);
    for (unsigned i = 0; i < count; ++i) {
        assert(DeviceConfigLoader_Load(names[i], &dev));
        assert(dev.coldGlycolPump.actuatorId && strcmp(dev.coldGlycolPump.actuatorId, "HVAC_COLD_GLYCOL_PUMP") == 0);
        assert(dev.coldGlycolValve.feedbackMultiplier == 1.0f);
        assert(dev.coldGlycolValve.setpointMax == 100.0f);
        assert(dev.coldGlycolValve.tickTimeMs == 100);
    }
    assert(!DeviceConfigLoader_Load("missing", &dev));
    DeviceConfigCmds cmd = {.configOps = &ops, .defaultConfigType="HvacDeviceConfig", .configName="X", .cmd=DEVICE_CONFIG_CMD_SAVE};
    DeviceConfigCmds_Update(&cmd); assert(cmd.error);
    Clocks clocks={.clock100ms=true};
    dev.coldGlycolPump.status=ACTUATOR_STATUS_ENABLED;
    dev.coldGlycolPump.enable=true;
    dev.coldGroupEnableRequest=true;
    DeviceManager_Update(&dev,&clocks,OPERATING_MODE_RUN);
    assert(!dev.coldGroupEnableRequest && dev.coldGlycolValve.enable);
    bool on=true, off=true;
    dev.coldGlycolPump.operationType = OPERATING_MODE_INIT;
    dev.coldGlycolPump.enableRequest=&on; dev.coldGlycolPump.disableRequest=&off;
    Actuator_Update(&dev.coldGlycolPump); assert(!on && !off && !dev.coldGlycolPump.notInitialized);
}
static void apply(const char *s, int n, void *dev) { JsonToParametersMapper_ParseAndApply(s,n,dev); }
static void test_json_mqtt(void) {
    DeviceFacade dev = {.tempSetpoint=1};
    const char *valid="{\"tempSetpoint\":23.5,\"unknown\":{\"tempSetpoint\":99}}";
    JsonToParametersMapper_ParseAndApply(valid, (int)strlen(valid), &dev); assert(dev.tempSetpoint == 23.5f);
    const char *bad="{\"tempSetpoint\":8,\"x\":";
    JsonToParametersMapper_ParseAndApply(bad,(int)strlen(bad),&dev); assert(dev.tempSetpoint == 23.5f);
    JsonToParametersMapper_Apply("tempSetpoint","nan",&dev); assert(dev.tempSetpoint == 23.5f);
    JsonToParametersMapper_Apply("minRuntime","-1",&dev); assert(dev.minRuntime == 0);
    JsonToParametersMapper_Apply("setPointTimeHigh","65536",&dev); assert(dev.setPointTimeHigh == 0);
    MqttParameterSub sub={.device=&dev,.parseFn=apply};
    MqttParameterSub_Update(&sub,true); assert(sub.subscribed);
    host_receive("otherliveParamsSub","{\"tempSetpoint\":99}");
    MqttParameterSub_Update(&sub,true); assert(dev.tempSetpoint == 23.5f);
    host_receive(MOQUI_LIVE_PARAMS_SUB_TOPIC,"{\"tempSetpoint\":17}"); assert(dev.tempSetpoint == 23.5f);
    MqttParameterSub_Update(&sub,true); assert(dev.tempSetpoint == 17);
    host_receive(MOQUI_LIVE_PARAMS_SUB_TOPIC,"{\"tempSetpoint\":99}");
    MqttParameterSub_Update(&sub,false); MqttParameterSub_Update(&sub,true); assert(dev.tempSetpoint == 17);
    assert(host_subscribes == 2);
    for (unsigned i=0;i<12;i++) { host_receive(MOQUI_LIVE_PARAMS_SUB_TOPIC,"{\"tempSetpoint\":18}"); }
    MqttParameterSub_Update(&sub,true); assert(sub.droppedMessages == 2 && dev.tempSetpoint == 18);
}
static void test_logs(void) {
    LoggerFacade logger={.enable=true,.loggerName="HVAC_DEMO_PLC"};
    LogEvent log; uint16_t count;
    LogEvent discard[10];
    do { LoggerFacade_DrainBuffer(discard,10,&count); } while (count);
    LoggerFacade_LogNumeric(&logger,LOG_LEVEL_INFO,"HvacTempSetpoint",23.5);
    LoggerFacade_DrainBuffer(&log,1,&count); assert(count==1);
    char json[2048];
    assert(serialize_log_event(&log,json,sizeof(json)));
    assert(JsonFields_Valid(json,strlen(json)) && strstr(json,"\"numericValue\":23.5"));
    assert(strstr(json,"\"loggerName\":\"HVAC_DEMO_PLC\""));
    log.payloadType=LOG_PAYLOAD_TYPE_TEXT;
    strcpy(log.payload.message,"quoted \"text\"\nbackslash \\");
    assert(serialize_log_event(&log,json,sizeof(json)) && JsonFields_Valid(json,strlen(json)));
    log.payloadType=LOG_PAYLOAD_TYPE_NUMERIC; log.payload.numericValue=NAN;
    assert(!serialize_log_event(&log,json,sizeof(json)));
    DeviceFacade dev={0}; Clocks clocks={.clock1minute=true};
    ParameterLogger_Update(&dev,&clocks,OPERATING_MODE_RUN);
    unsigned total=0;
    do { LoggerFacade_DrainBuffer(discard,10,&count); total+=count; } while (count);
    assert(total==29);
    uint16_t out=123;
    assert(!processAnalogOutput(10,0,100,0,100,0,0,0,true,NULL,&out,NULL) && out==123);
    bool en,dis,fault;
    assert(!processCyclicInFieldbusData(ACTUATOR_MODEL_CTM700,FIELDBUS_PROTOCOL_MODBUS_TCP,0,&en,&dis,&fault));
}
int main(void) {
    test_clocks(); test_start(); test_recipes(); test_json_mqtt(); test_logs();
    HvacTestSuite suite={0};
    for (unsigned i=0; i<100000 && !suite.testDone && !suite.testFailed; ++i) {
        suite.clks.clock10ms=true; suite.clks.clock100ms=i%10==0; suite.clks.clock1s=i%100==0;
        HvacTestSuite_Update(&suite);
    }
    if (suite.testFailed) { fprintf(stderr,"HVAC failure %u\n",suite.failStep); }
    assert(suite.testDone && !suite.testFailed);
    for (unsigned i=1; i<=HVAC_TEST_PASS_COUNT; ++i) { assert(suite.pass[i]); }
    puts("IoT runtime regressions and all HVAC scenarios passed");
    return 0;
}

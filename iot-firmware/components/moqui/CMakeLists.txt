idf_build_get_property(target IDF_TARGET)

set(FRAMEWORK  "framework/src/main/org/moqui")
set(HVAC       "runtime/component/mantle-hvac/src/main")
set(HVAC_TEST  "runtime/component/mantle-hvac/src/test")
set(UDM_ENTITY "runtime/component/mantle-udm/src/main/org/moqui/entity")

if(NOT ${target} STREQUAL "linux")
    set(_platform_requires "mqtt" "esp_netif" "esp_hw_support" "esp_timer" "nvs_flash")
    set(_platform_srcs
        "platform/esp32/mqtt_platform.c"
        "platform/esp32/net_platform.c"
        "platform/esp32/time_platform.c"
    )
else()
    set(_platform_requires "")
    set(_platform_srcs "")
endif()

if(CONFIG_MOQUI_ENABLE_TEST_SUITE)
    set(_test_srcs "${HVAC_TEST}/HvacTestSuite.c")
    set(_test_includes "${HVAC_TEST}")
else()
    set(_test_srcs "")
    set(_test_includes "")
endif()

idf_component_register(
    SRCS
        # platform abstraction layer (ESP32 implementation)
        ${_platform_srcs}

        # context
        "${FRAMEWORK}/context/ec.c"
        "${FRAMEWORK}/context/LoggerFacade.c"

        # device
        "${FRAMEWORK}/device/Actuator.c"
        "${FRAMEWORK}/device/ActuatorGroup.c"
        "${FRAMEWORK}/device/DeviceConfigCmds.c"
        "${FRAMEWORK}/device/DeviceConfigMgmt.c"
        "${FRAMEWORK}/device/EdgeTrigStatusMgr.c"
        "${FRAMEWORK}/device/Fieldbus_Analog.c"
        "${FRAMEWORK}/device/InputSignalUpdate.c"
        "${FRAMEWORK}/device/LevelCtrlStatusMgr.c"
        "${FRAMEWORK}/device/OutputSignalUpdate.c"
        "${FRAMEWORK}/device/ProcessPid.c"
        "${FRAMEWORK}/device/RecipeManagerCmds.c"

        # diagnostics
        "${FRAMEWORK}/diagnostics/NetworkDiagnostics.c"
        "${FRAMEWORK}/diagnostics/RemoteIoModuleDiagnostics.c"
        "${FRAMEWORK}/diagnostics/SignalMgmt.c"

        # mqtt (MqttConnectionFactory.c is in _platform_srcs — ESP32 only)
        "${FRAMEWORK}/mqtt/MqttClient.c"
        "${FRAMEWORK}/mqtt/MqttLogAppender.c"
        "${FRAMEWORK}/mqtt/MqttParameterPub.c"
        "${FRAMEWORK}/mqtt/MqttParameterSub.c"

        # start
        "${FRAMEWORK}/start/configuration.c"
        "${FRAMEWORK}/start/MoquiStart.c"

        # util
        "${FRAMEWORK}/util/ClockGeneration.c"
        "${FRAMEWORK}/util/EndianUtils.c"
        "${FRAMEWORK}/util/Filter.c"
        "${FRAMEWORK}/util/IIRFilter.c"
        "${FRAMEWORK}/util/MathUtils.c"
        "${FRAMEWORK}/util/MeanFilter.c"
        "${FRAMEWORK}/util/round.c"
        "${FRAMEWORK}/util/scale.c"
        "${FRAMEWORK}/util/SShapedFunc.c"
        "${FRAMEWORK}/util/truncReal.c"
        "${FRAMEWORK}/util/TypeUtils.c"

        # runtime/mantle-hvac — device components
        "${HVAC}/org/moqui/device/AirDistributionController.c"
        "${HVAC}/org/moqui/device/DeviceDiagnostics.c"
        "${HVAC}/org/moqui/device/DeviceManager.c"

        # runtime/mantle-hvac — JSON utilities
        "${HVAC}/org/moqui/util/json/JsonToParametersMapper.c"
        "${HVAC}/org/moqui/util/json/ParametersToJsonMapper.c"

        # runtime/mantle-hvac — main control loop
        "${HVAC}/mantle/hvac/MainRuleEngine.c"
        "${HVAC}/mantle/hvac/Main.c"
        "${HVAC}/mantle/hvac/DeviceConfigLoader.c"
        "${HVAC}/mantle/hvac/HvacDeviceConfigOps.c"

        # runtime/mantle-hvac — tests (conditional on MOQUI_ENABLE_TEST_SUITE)
        ${_test_srcs}

    EMBED_TXTFILES
        "runtime/component/mantle-hvac/data/Phase1HvacCooling.HvacDeviceConfig.json"
        "runtime/component/mantle-hvac/data/Phase2HvacDrying.HvacDeviceConfig.json"
        "runtime/component/mantle-hvac/data/Phase3HvacHeating.HvacDeviceConfig.json"
        "runtime/component/mantle-hvac/data/Phase4HvacDrying_Progressive.HvacDeviceConfig.json"
        "runtime/component/mantle-hvac/data/Phase5HvacDrying_Intensive.HvacDeviceConfig.json"
        "runtime/component/mantle-hvac/data/TestRecipes.json"

    INCLUDE_DIRS
        # platform abstraction layer
        "platform"

        # framework — resources (MoquiConf.h)
        "framework/src/main/resources"

        # framework — component dirs
        "${FRAMEWORK}/context"
        "${FRAMEWORK}/device"
        "${FRAMEWORK}/diagnostics"
        "${FRAMEWORK}/mqtt"
        "${FRAMEWORK}/start"
        "${FRAMEWORK}/util"

        # runtime/mantle-hvac — device and utility headers
        "${HVAC}/org/moqui/device"
        "${HVAC}/org/moqui/util/json"
        "${HVAC}/mantle/hvac"

        # runtime/mantle-hvac — tests (conditional on MOQUI_ENABLE_TEST_SUITE)
        ${_test_includes}

        # runtime/mantle-udm — entity models
        "${UDM_ENTITY}"

    REQUIRES ${_platform_requires}
)

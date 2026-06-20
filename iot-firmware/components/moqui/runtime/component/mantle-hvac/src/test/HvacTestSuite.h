#ifndef HVAC_TEST_SUITE_H
#define HVAC_TEST_SUITE_H

#include <stdint.h>
#include <stdbool.h>
#include "DeviceFacade.h"
#include "Clocks.h"
#include "Main.h"
#include "MainStatus.h"

#define HVAC_TEST_PASS_COUNT (32U)

typedef struct {
    /* Test infrastructure */
    uint16_t step;
    uint16_t cycles;
    bool     testDone;
    bool     testFailed;
    uint16_t failStep;
    bool     testReset;
    bool     init;
    bool     pass[HVAC_TEST_PASS_COUNT + 1U]; /* 1-indexed; [0] unused */

    /* Device under test and clocks */
    DeviceFacade dev;
    Clocks       clks;

    /* Diagnostic mirrors */
    MainStatus mirStatus;
    bool       mirColdGroupEnable;
    bool       mirHotGroupEnable;
    bool       mirAhuFanEnable;
    bool       mirAirFlowEnable;
    bool       mirFaultRequest;
    bool       mirStandbyRequest;
    bool       mirCoolingRequest;
    bool       mirHeatingRequest;
    bool       mirDryingRequest;
    bool       mirTempInRange;
    bool       mirTempOverMax;
    bool       mirTempUnderMin;
    bool       mirDuctTempOverMax;
    bool       mirDuctTempUnderMin;
    bool       mirTimeBreakEnabled;
    MainStatus mirLastStatus;
    uint32_t   mirActualRuntime;
} HvacTestSuite;

void HvacTestSuite_Update(HvacTestSuite *suite);

#endif /* HVAC_TEST_SUITE_H */

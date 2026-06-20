#ifndef CLOCK_GENERATION_H
#define CLOCK_GENERATION_H

#include <stdint.h>
#include <stdbool.h>
#include "Clocks.h"
#include "OperatingMode.h"

/*
 * Clock pulse generation from a 10 ms system tick.
 * Faithful port of ClockGeneration.st (FUNCTION_BLOCK ClockGeneration).
 *
 * Call ClockGeneration_Update once per task cycle.
 * The Clocks struct is written in-place (mirrors VAR_EXTERNAL clks in ST).
 */
typedef struct {
    /* VAR_INPUT */
    OperatingMode operationType;

    /* VAR — internal counters */
    bool     systemClockOld;
    uint32_t timerClock100ms;
    uint32_t timerClock1s;
    uint32_t timerClock1minute;

} ClockGeneration;

void ClockGeneration_Update(ClockGeneration *self, Clocks *clks);

#endif /* CLOCK_GENERATION_H */

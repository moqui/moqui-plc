#include "ClockGeneration.h"

void ClockGeneration_Update(ClockGeneration *self, Clocks *clks)
{
    if (self->operationType == OPERATING_MODE_INIT) {
        self->systemClockOld    = true;
        self->timerClock100ms   = 10U;
        self->timerClock1s      = 10U;
        self->timerClock1minute = 60U;
    }

    /* clock10ms is always TRUE: full-speed 10 ms cycle tick */
    clks->clock10ms = true;

    if (clks->clock10ms && (self->timerClock100ms > 0U)) {
        self->timerClock100ms--;
    }
    clks->clock100ms = (self->timerClock100ms == 0U);

    if (clks->clock100ms) {
        self->timerClock100ms = 10U;
        if (self->timerClock1s > 0U) {
            self->timerClock1s--;
        }
    }
    clks->clock1s = (self->timerClock1s == 0U);

    if (clks->clock1s) {
        self->timerClock1s = 10U;
        if (self->timerClock1minute > 0U) {
            self->timerClock1minute--;
        }
    }
    clks->clock1minute = (self->timerClock1minute == 0U);

    if (clks->clock1minute) {
        self->timerClock1minute = 60U;
    }
}

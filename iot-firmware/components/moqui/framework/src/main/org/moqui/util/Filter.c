#include "Filter.h"

void Filter_Update(Filter *filter) {
    if (filter->operationType == OPERATING_MODE_INIT) {
        filter->delay = 0;
    }

    if (filter->clock && filter->delay > 0) {
        filter->delay--;
    }

    if (filter->delay == 0) {
        filter->delayedSignal = filter->signal;
    }

    if (filter->signal == filter->delayedSignal) {
        if (filter->signal) {
            filter->delay = filter->deactivationDelay;
        } else {
            filter->delay = filter->activationDelay;
        }
    }
}

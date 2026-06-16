#ifndef FILTER_H
#define FILTER_H

#include <stdint.h>
#include <stdbool.h>
#include "OperatingMode.h"

typedef struct {
    /* VAR_INPUT */
    OperatingMode operationType;
    bool clock;
    bool signal;
    uint32_t activationDelay;
    uint32_t deactivationDelay;

    /* VAR_OUTPUT */
    bool delayedSignal;

    /* VAR */
    uint32_t delay;

} Filter;

void Filter_Update(Filter *filter);

#endif /* FILTER_H */

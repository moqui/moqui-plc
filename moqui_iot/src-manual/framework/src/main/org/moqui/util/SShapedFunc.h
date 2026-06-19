#ifndef S_SHAPED_FUNC_H
#define S_SHAPED_FUNC_H

#include <stdint.h>
#include <stdbool.h>

/*
 * S-shaped (cubic Hermite) ramp from startValue to endValue over duration.
 * Faithful port of SShapedFunc.st (FUNCTION_BLOCK SShapedFunc).
 *
 * Formula: output = start + delta * (3*p^2 - 2*p^3)  where p in [0,1].
 * PLCopen edge-triggered pattern: starts on rising edge of execute.
 */
typedef struct {
    /* VAR_INPUT */
    bool     execute;     /* PLCopen: start on rising edge */
    bool     clock;       /* Tick pulse (one-cycle TRUE) */
    float    startValue;
    float    endValue;
    uint32_t durationMs;  /* Total ramp duration in milliseconds */
    uint32_t tickTimeMs;  /* Sampling period in milliseconds (default 10) */

    /* VAR_OUTPUT */
    float   output;
    bool    done;
    bool    busy;
    bool    error;
    int16_t errorId; /* 1: InvalidTime */

    /* VAR — internal state */
    bool     prevExecute;
    bool     active;
    uint32_t elapsedTicks;
    uint32_t totalTicks;
    float    deltaValue;

} SShapedFunc;

void SShapedFunc_Update(SShapedFunc *self);

#endif /* S_SHAPED_FUNC_H */

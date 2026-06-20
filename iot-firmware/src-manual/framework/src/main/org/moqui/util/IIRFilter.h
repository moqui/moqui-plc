#ifndef IIR_FILTER_H
#define IIR_FILTER_H

#include <stdint.h>
#include <stdbool.h>

/*
 * First-order IIR low-pass filter (exponential moving average).
 * Faithful port of IIRFilter.st (FUNCTION_BLOCK IIRFilter).
 *
 * Algorithm:
 *   alpha = 1 - exp(-deltaTime / T)   where deltaTime = tickTime_ms / 1000.0
 *   output += alpha * (input - output)
 *
 * Call IIRFilter_Update once per clock tick (when clock is TRUE).
 */
typedef struct {
    /* VAR_INPUT */
    bool     execute;    /* Enable filter computation */
    bool     clock;      /* Tick pulse (one-cycle TRUE) */
    bool     reset;      /* Force re-initialisation */
    float    input;      /* Filter input */
    float    T;          /* Time constant in seconds (> 0) */
    uint32_t tickTimeMs; /* Sampling period in milliseconds (> 0, default 10) */

    /* VAR_OUTPUT */
    float output;
    bool  done;
    bool  busy;
    bool  error;
    int16_t errorId; /* 1: InvalidTime (tickTimeMs <= 0 or T <= 0) */
    float timeElapsed; /* Elapsed time in seconds since last reset */

    /* VAR — internal state */
    bool     init;
    uint32_t elapsedTicks;

} IIRFilter;

void IIRFilter_Update(IIRFilter *self);

#endif /* IIR_FILTER_H */

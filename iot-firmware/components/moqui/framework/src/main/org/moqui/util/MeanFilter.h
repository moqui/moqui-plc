#ifndef MEAN_FILTER_H
#define MEAN_FILTER_H

#include <stdint.h>
#include <stdbool.h>
#include "MeanFilterType.h"

/*
 * Mean / Moving Average Filter: SMA, WMA_Ramp, WMA_Triangular(+OddOnly), TRI_SMA2, EMA.
 * Faithful port of MeanFilter.st (FUNCTION_BLOCK MeanFilter).
 *
 * Config changes (filterType or windowSize) force an internal reset automatically.
 */

#define MEAN_FILTER_MAX_WINDOW (256U)

typedef struct {
    /* VAR_INPUT */
    bool           execute;
    bool           clock;
    bool           reset;
    float          input;
    MeanFilterType filterType;
    uint16_t       windowSize; /* Must be 1..MEAN_FILTER_MAX_WINDOW */
    float          emaAlpha;   /* EMA only: must be in (0, 1] */

    /* VAR_OUTPUT */
    float   output;
    bool    done;
    bool    busy;
    bool    error;
    int16_t errorId; /* 1: InvalidWindow, 3: InvalidAlpha, 4: RequiresOddWindow */

    /* VAR — ring buffer (SMA / WMA_Ramp / WMA_Triangular) */
    float    buffer[MEAN_FILTER_MAX_WINDOW];
    uint16_t idx;
    bool     initialized;

    /* SMA accumulator */
    float sumSma;

    /* WMA_Ramp */
    float wsumRamp;
    float denomRamp;
    float sumOldRamp;

    /* TRI_SMA2 */
    float    sma2Buf1[MEAN_FILTER_MAX_WINDOW];
    float    sma2Buf2[MEAN_FILTER_MAX_WINDOW];
    uint16_t sma2Idx1;
    uint16_t sma2Idx2;
    float    sma2Sum1;
    float    sma2Sum2;
    float    sma2Y1;
    float    sma2Y2;
    bool     sma2Init;

    /* EMA */
    float emaY;

    /* Config change detection */
    MeanFilterType prevType;
    uint16_t       prevWindow;

} MeanFilter;

void MeanFilter_Update(MeanFilter *self);

#endif /* MEAN_FILTER_H */

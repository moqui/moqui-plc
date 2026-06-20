#include "MeanFilter.h"

/* -------------------------------------------------------------------------
 * Internal: reset all state variables
 * ---------------------------------------------------------------------- */
static void mean_filter_reset(MeanFilter *self)
{
    uint16_t i;

    self->idx         = 1U;
    self->initialized = false;
    self->sumSma      = 0.0f;
    self->wsumRamp    = 0.0f;
    self->denomRamp   = 0.0f;
    self->sumOldRamp  = 0.0f;
    self->emaY        = 0.0f;
    self->sma2Idx1    = 1U;
    self->sma2Idx2    = 1U;
    self->sma2Sum1    = 0.0f;
    self->sma2Sum2    = 0.0f;
    self->sma2Y1      = 0.0f;
    self->sma2Y2      = 0.0f;
    self->sma2Init    = false;

    for (i = 0U; i < MEAN_FILTER_MAX_WINDOW; i++) {
        self->buffer[i]   = 0.0f;
        self->sma2Buf1[i] = 0.0f;
        self->sma2Buf2[i] = 0.0f;
    }
}

/* -------------------------------------------------------------------------
 * MeanFilter_Update
 * ---------------------------------------------------------------------- */
void MeanFilter_Update(MeanFilter *self)
{
    float    xOld;
    float    xNew;
    float    wsumTri;
    float    denomTri;
    float    w;
    float    distF;
    uint16_t mid;
    uint16_t k;
    uint16_t pos;
    uint16_t i;
    uint16_t n;

    self->done    = false;
    self->busy    = false;
    self->error   = false;
    self->errorId = 0;

    /* Config change forces reset (mirrors ST behaviour) */
    if ((self->filterType != self->prevType) ||
        (self->windowSize != self->prevWindow)) {
        self->reset = true;
    }
    self->prevType   = self->filterType;
    self->prevWindow = self->windowSize;

    /* Input validation */
    switch (self->filterType) {
        case MEAN_FILTER_TYPE_SMA:
        case MEAN_FILTER_TYPE_WMA_RAMP:
        case MEAN_FILTER_TYPE_WMA_TRIANGULAR:
        case MEAN_FILTER_TYPE_WMA_TRIANGULAR_ODD_ONLY:
        case MEAN_FILTER_TYPE_TRI_SMA2:
            if ((self->windowSize == 0U) || (self->windowSize > MEAN_FILTER_MAX_WINDOW)) {
                self->error   = self->execute;
                self->errorId = 1; /* InvalidWindow */
                return;
            }
            if ((self->filterType == MEAN_FILTER_TYPE_WMA_TRIANGULAR_ODD_ONLY) &&
                ((self->windowSize % 2U) == 0U)) {
                self->error   = self->execute;
                self->errorId = 4; /* RequiresOddWindow */
                return;
            }
            break;

        case MEAN_FILTER_TYPE_EMA:
            if ((self->emaAlpha <= 0.0f) || (self->emaAlpha > 1.0f)) {
                self->error   = self->execute;
                self->errorId = 3; /* InvalidAlpha */
                return;
            }
            break;

        default:
            break;
    }

    if (self->reset) {
        mean_filter_reset(self);
    }

    if (!self->execute) {
        self->busy = false;
        self->done = false;
        return;
    }

    self->busy = true;
    n = self->windowSize;

    switch (self->filterType) {
        case MEAN_FILTER_TYPE_SMA:
            if (!self->initialized) {
                for (i = 0U; i < n; i++) {
                    self->buffer[i] = self->input;
                }
                self->sumSma     = self->input * (float)n;
                self->idx        = 0U;
                self->initialized = true;
                self->output     = self->input;
            } else if (self->clock) {
                xOld = self->buffer[self->idx];
                self->buffer[self->idx] = self->input;
                self->sumSma = self->sumSma - xOld + self->input;
                self->idx++;
                if (self->idx >= n) { self->idx = 0U; }
                self->output = self->sumSma / (float)n;
            } else {
                /* no update */
            }
            break;

        case MEAN_FILTER_TYPE_WMA_RAMP:
            if (!self->initialized) {
                for (i = 0U; i < n; i++) {
                    self->buffer[i] = self->input;
                }
                self->denomRamp = (float)n * (float)(n + 1U) / 2.0f;
                self->sumSma    = self->input * (float)n;
                self->wsumRamp  = self->input * self->denomRamp;
                self->idx       = 0U;
                self->initialized = true;
                self->output    = self->input;
            } else if (self->clock) {
                xOld             = self->buffer[self->idx];
                xNew             = self->input;
                self->sumOldRamp = self->sumSma;
                self->buffer[self->idx] = xNew;
                self->sumSma   = self->sumSma - xOld + xNew;
                /* W' = W - S_old + N * xNew */
                self->wsumRamp = self->wsumRamp - self->sumOldRamp +
                                 ((float)n * xNew);
                self->idx++;
                if (self->idx >= n) { self->idx = 0U; }
                self->output = self->wsumRamp / self->denomRamp;
            } else {
                /* no update */
            }
            break;

        case MEAN_FILTER_TYPE_WMA_TRIANGULAR:
        case MEAN_FILTER_TYPE_WMA_TRIANGULAR_ODD_ONLY:
            if (!self->initialized) {
                for (i = 0U; i < n; i++) {
                    self->buffer[i] = self->input;
                }
                self->idx         = 0U;
                self->initialized = true;
                self->output      = self->input;
            }
            if (self->clock) {
                self->buffer[self->idx] = self->input;
                self->idx++;
                if (self->idx >= n) { self->idx = 0U; }

                mid      = (n + 1U) / 2U;
                wsumTri  = 0.0f;
                denomTri = 0.0f;

                for (i = 0U; i < n; i++) {
                    pos = (uint16_t)(self->idx + i);
                    if (pos >= n) { pos -= n; }
                    k = i + 1U;
                    distF = (k >= mid) ? (float)(k - mid) : (float)(mid - k);
                    w     = (float)mid - distF;
                    wsumTri  += w * self->buffer[pos];
                    denomTri += w;
                }

                self->output = (denomTri > 0.0f) ?
                               (wsumTri / denomTri) : self->input;
            }
            break;

        case MEAN_FILTER_TYPE_TRI_SMA2:
            if (!self->sma2Init) {
                for (i = 0U; i < n; i++) {
                    self->sma2Buf1[i] = self->input;
                    self->sma2Buf2[i] = self->input;
                }
                self->sma2Sum1 = self->input * (float)n;
                self->sma2Sum2 = self->input * (float)n;
                self->sma2Idx1 = 0U;
                self->sma2Idx2 = 0U;
                self->sma2Y1   = self->input;
                self->sma2Y2   = self->input;
                self->sma2Init = true;
                self->output   = self->input;
            } else if (self->clock) {
                /* SMA stage 1 */
                xOld = self->sma2Buf1[self->sma2Idx1];
                self->sma2Buf1[self->sma2Idx1] = self->input;
                self->sma2Sum1 = self->sma2Sum1 - xOld + self->input;
                self->sma2Idx1++;
                if (self->sma2Idx1 >= n) { self->sma2Idx1 = 0U; }
                self->sma2Y1 = self->sma2Sum1 / (float)n;

                /* SMA stage 2 */
                xOld = self->sma2Buf2[self->sma2Idx2];
                self->sma2Buf2[self->sma2Idx2] = self->sma2Y1;
                self->sma2Sum2 = self->sma2Sum2 - xOld + self->sma2Y1;
                self->sma2Idx2++;
                if (self->sma2Idx2 >= n) { self->sma2Idx2 = 0U; }
                self->sma2Y2 = self->sma2Sum2 / (float)n;
                self->output = self->sma2Y2;
            } else {
                /* no update */
            }
            break;

        case MEAN_FILTER_TYPE_EMA:
            if (!self->initialized) {
                self->emaY        = self->input;
                self->initialized = true;
            } else if (self->clock) {
                self->emaY = self->emaY + self->emaAlpha * (self->input - self->emaY);
            } else {
                /* no update */
            }
            self->output = self->emaY;
            break;

        default:
            /* Unreachable with a well-formed enum */
            break;
    }

    self->done = !self->error;
}

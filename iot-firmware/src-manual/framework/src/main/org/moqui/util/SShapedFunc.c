#include "SShapedFunc.h"

void SShapedFunc_Update(SShapedFunc *self)
{
    float    progress;
    uint32_t totalTicks;

    /* Defaults */
    self->done  = false;
    self->busy  = false;
    self->error = (self->errorId != 0);

    /* Rising-edge detection */
    if (self->execute && (!self->prevExecute)) {
        self->errorId = 0; /* Clear previous error on new rising edge */

        if ((self->durationMs == 0U) || (self->tickTimeMs == 0U)) {
            self->error   = true;
            self->errorId = 1; /* InvalidTime */
            self->active  = false;
        } else {
            self->active = true;
            self->elapsedTicks = 0U;

            totalTicks = self->durationMs / self->tickTimeMs;
            self->totalTicks = (totalTicks == 0U) ? 1U : totalTicks;

            self->deltaValue = self->endValue - self->startValue;
            self->output     = self->startValue;
        }
    }

    if (self->execute) {
        if (self->active) {
            self->busy = true;

            if (self->clock) {
                if (self->elapsedTicks < self->totalTicks) {
                    self->elapsedTicks++;
                }
            }

            progress = (float)self->elapsedTicks / (float)self->totalTicks;

            if (progress >= 1.0f) {
                self->output = self->endValue;
                self->active = false;
                self->done   = true;
            } else {
                /* Cubic Hermite: 3p^2 - 2p^3 */
                self->output = self->startValue +
                               self->deltaValue *
                               (3.0f * progress * progress -
                                2.0f * progress * progress * progress);
            }
        } else {
            if (!self->error) {
                self->done = true;
            }
        }
    } else {
        /* Reset when execute is FALSE */
        self->active       = false;
        self->elapsedTicks = 0U;
        self->totalTicks   = 0U;
        self->errorId      = 0;
    }

    self->prevExecute = self->execute;
}

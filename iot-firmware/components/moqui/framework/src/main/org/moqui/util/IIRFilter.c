#include "IIRFilter.h"

#include <math.h>

void IIRFilter_Update(IIRFilter *self)
{
    float deltaTime;
    float alpha;

    /* Defaults */
    self->done    = false;
    self->busy    = false;
    self->error   = false;
    self->errorId = 0;

    /* Validate tickTime */
    if (self->tickTimeMs == 0U) {
        self->error   = self->execute;
        self->errorId = 1; /* InvalidTime */
        self->busy    = false;
        return;
    }

    deltaTime = (float)self->tickTimeMs / 1000.0f; /* seconds per tick */

    if (self->reset) {
        self->init         = false;
        self->elapsedTicks = 0U;
    }

    if (self->execute) {
        self->busy = true;

        /* Initialise output to current input on first enable */
        if (!self->init) {
            self->output       = self->input;
            self->init         = true;
            self->elapsedTicks = 0U;
        } else {
            /* Update only on clock tick */
            if (self->clock) {
                if (self->T > 0.0f) {
                    /* alpha = 1 - exp(-dt / T) */
                    alpha        = 1.0f - expf(-deltaTime / self->T);
                    self->output = self->output + alpha * (self->input - self->output);
                } else {
                    /* T <= 0: pass-through (same as ST behaviour when T = 0) */
                    self->output = self->input;
                }
                self->elapsedTicks++;
            }
        }

        self->timeElapsed = (float)self->elapsedTicks * deltaTime;
        self->done        = !self->error;
    } else {
        self->busy        = false;
        self->done        = false;
        self->timeElapsed = 0.0f;
    }
}

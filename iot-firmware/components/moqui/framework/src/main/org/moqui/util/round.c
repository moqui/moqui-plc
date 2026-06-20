#include "round.h"

#include <math.h>

float roundReal(float inputValue, int16_t decimals)
{
    float factor;
    float temp;
    float result;

    factor = powf(10.0f, (float)decimals);
    temp   = inputValue * factor;

    if (temp >= 0.0f) {
        result = truncf(temp + 0.5f) / factor;
    } else {
        result = truncf(temp - 0.5f) / factor;
    }

    return result;
}

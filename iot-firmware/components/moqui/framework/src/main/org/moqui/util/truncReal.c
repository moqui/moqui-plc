#include "truncReal.h"

#include <math.h>

float truncReal(float inputValue, int16_t decimals)
{
    float factor;

    factor = powf(10.0f, (float)decimals);
    return truncf(inputValue * factor) / factor;
}

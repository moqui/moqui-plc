#include "MathUtils.h"
#include <math.h>

float util_round(float value, int16_t significantDigits) {
    if (significantDigits == 0) return roundf(value);
    float factor = powf(10.0f, (float)significantDigits);
    return roundf(value * factor) / factor;
}

float util_scale(float value, float min_in, float max_in, float min_out, float max_out) {
    if (max_in == min_in) return min_out;
    return min_out + (value - min_in) * (max_out - min_out) / (max_in - min_in);
}

float util_truncReal(float value, int16_t significantDigits) {
    if (significantDigits == 0) return truncf(value);
    float factor = powf(10.0f, (float)significantDigits);
    return truncf(value * factor) / factor;
}

float util_trim(float value, float min_val, float max_val) {
    if (value < min_val) return min_val;
    if (value > max_val) return max_val;
    return value;
}

float util_SShapedFunc(float x, float x0, float L, float k) {
    /* Standard logistic function: f(x) = L / (1 + e^(-k(x-x0))) */
    return L / (1.0f + expf(-k * (x - x0)));
}

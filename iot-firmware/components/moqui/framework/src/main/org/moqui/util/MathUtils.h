#ifndef MATH_UTILS_H
#define MATH_UTILS_H

#include <stdint.h>

float util_round(float value, int16_t significantDigits);
float util_scale(float value, float min_in, float max_in, float min_out, float max_out);
float util_truncReal(float value, int16_t significantDigits);
float util_trim(float value, float min_val, float max_val);
float util_SShapedFunc(float x, float x0, float L, float k);

#endif /* MATH_UTILS_H */

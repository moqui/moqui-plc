#ifndef TRUNC_REAL_H
#define TRUNC_REAL_H

#include <stdint.h>

/*
 * Truncate inputValue to the given number of decimal places (no rounding).
 * Faithful port of truncReal.st (FUNCTION truncReal).
 */
float truncReal(float inputValue, int16_t decimals);

#endif /* TRUNC_REAL_H */

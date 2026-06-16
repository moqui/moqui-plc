#ifndef ROUND_H
#define ROUND_H

#include <stdint.h>

/*
 * Round inputValue to the given number of decimal places.
 * Faithful port of round.st (FUNCTION round).
 * Positive decimals: round to that many decimal places.
 * Negative decimals: round to tens, hundreds, etc.
 */
float roundReal(float inputValue, int16_t decimals);

#endif /* ROUND_H */

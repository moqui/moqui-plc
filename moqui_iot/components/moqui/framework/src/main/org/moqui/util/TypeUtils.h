#ifndef TYPE_UTILS_H
#define TYPE_UTILS_H

#include <stdint.h>

float doubleWordToReal(uint32_t input);
double longWordToLongReal(uint64_t input);
void realToWordArray(float input, uint16_t *outputArray);
void longRealToWordArray(double input, uint16_t *outputArray);
void toByteArray(uint16_t inputWord, uint8_t *byteArray);

#endif /* TYPE_UTILS_H */

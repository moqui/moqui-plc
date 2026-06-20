#include "TypeUtils.h"
#include <string.h>

float doubleWordToReal(uint32_t input) {
    float output;
    memcpy(&output, &input, sizeof(float));
    return output;
}

double longWordToLongReal(uint64_t input) {
    double output;
    memcpy(&output, &input, sizeof(double));
    return output;
}

void realToWordArray(float input, uint16_t *outputArray) {
    uint32_t temp;
    memcpy(&temp, &input, sizeof(float));
    outputArray[0] = (uint16_t)(temp & 0xFFFF);
    outputArray[1] = (uint16_t)((temp >> 16) & 0xFFFF);
}

void longRealToWordArray(double input, uint16_t *outputArray) {
    uint64_t temp;
    memcpy(&temp, &input, sizeof(double));
    outputArray[0] = (uint16_t)(temp & 0xFFFF);
    outputArray[1] = (uint16_t)((temp >> 16) & 0xFFFF);
    outputArray[2] = (uint16_t)((temp >> 32) & 0xFFFF);
    outputArray[3] = (uint16_t)((temp >> 48) & 0xFFFF);
}

void toByteArray(uint16_t inputWord, uint8_t *byteArray) {
    byteArray[0] = (uint8_t)(inputWord & 0xFF);
    byteArray[1] = (uint8_t)((inputWord >> 8) & 0xFF);
}

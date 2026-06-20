#include "scale.h"

float scale(float inputValue,
            float minInputValue, float maxInputValue,
            float minOutputValue, float maxOutputValue)
{
    float clamped;
    float outputValue;

    if (maxInputValue <= minInputValue) {
        outputValue = minOutputValue;
    } else {
        /* Clamp input to [min, max] */
        if (inputValue < minInputValue) {
            clamped = minInputValue;
        } else if (inputValue > maxInputValue) {
            clamped = maxInputValue;
        } else {
            clamped = inputValue;
        }

        outputValue = ((maxOutputValue - minOutputValue) /
                       (maxInputValue  - minInputValue)) *
                      (clamped - minInputValue) + minOutputValue;
    }

    return outputValue;
}

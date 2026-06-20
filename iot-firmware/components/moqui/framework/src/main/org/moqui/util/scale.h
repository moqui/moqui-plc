#ifndef SCALE_H
#define SCALE_H

/*
 * Linear scaling of inputValue from [minInput, maxInput] to [minOutput, maxOutput].
 * Faithful port of scale.st (FUNCTION scale).
 * Input is clamped to [minInput, maxInput] before scaling.
 */
float scale(float inputValue,
            float minInputValue, float maxInputValue,
            float minOutputValue, float maxOutputValue);

#endif /* SCALE_H */

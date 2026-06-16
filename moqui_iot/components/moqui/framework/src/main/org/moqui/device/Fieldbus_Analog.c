#include "Fieldbus_Analog.h"
#include <math.h>

float scale_value(float value, float min_in, float max_in, float min_out, float max_out) {
    if (max_in == min_in) return min_out;
    return min_out + (value - min_in) * (max_out - min_out) / (max_in - min_in);
}

float processAnalogInput(uint16_t physicalValue, uint16_t minPhysicalValue, uint16_t maxPhysicalValue, 
                         float minValue, float maxValue, float offset, float scalingFactor, int16_t significantDigits) {
    float inputValue = (float)physicalValue;
    inputValue = scale_value(inputValue, (float)minPhysicalValue, (float)maxPhysicalValue, minValue, maxValue);
    inputValue = inputValue * scalingFactor + offset;
    
    if (inputValue < minValue) inputValue = minValue;
    if (inputValue > maxValue) inputValue = maxValue;

    if (significantDigits == 0) {
        inputValue = truncf(inputValue);
    } else if (significantDigits > 0) {
        float factor = powf(10.0f, significantDigits);
        inputValue = roundf(inputValue * factor) / factor;
    }

    return inputValue;
}

bool processAnalogOutput(float parameterValue, uint16_t minPhysicalValue, uint16_t maxPhysicalValue, 
                         float minValue, float maxValue, float offset, float scalingFactor, 
                         int16_t significantDigits, bool littleEndian, 
                         uint8_t *byteAnalogOutput, uint16_t *wordAnalogOutput, uint32_t *dWordAnalogOutput) {
    float outputValue = (parameterValue - offset) / scalingFactor;
    
    if (outputValue < minValue) outputValue = minValue;
    if (outputValue > maxValue) outputValue = maxValue;
    
    outputValue = scale_value(outputValue, minValue, maxValue, (float)minPhysicalValue, (float)maxPhysicalValue);

    if (significantDigits == 0) {
        outputValue = truncf(outputValue);
    } else if (significantDigits > 0) {
        float factor = powf(10.0f, significantDigits);
        outputValue = roundf(outputValue * factor) / factor;
    }

    if (byteAnalogOutput) *byteAnalogOutput = (uint8_t)outputValue;

    if (littleEndian) {
        if (wordAnalogOutput) *wordAnalogOutput = (uint16_t)outputValue;
        if (dWordAnalogOutput) *dWordAnalogOutput = (uint32_t)outputValue;
    } else {
        if (wordAnalogOutput) *wordAnalogOutput = __builtin_bswap16((uint16_t)outputValue);
        if (dWordAnalogOutput) *dWordAnalogOutput = __builtin_bswap32((uint32_t)outputValue);
    }

    return true;
}

bool processCyclicInFieldbusData(ActuatorModel model, FieldbusProtocol fieldbus, uint16_t statusWord, 
                                 bool *enabledSensor, bool *disabledSensor, bool *externalFault) {
    *enabledSensor = false;
    *disabledSensor = false;
    *externalFault = false;

    switch (model) {
        case ACTUATOR_MODEL_ABBACH580:
            *enabledSensor = (statusWord & (1 << 0)) && (statusWord & (1 << 1)) && (statusWord & (1 << 2));
            *disabledSensor = !(statusWord & (1 << 0)) || !(statusWord & (1 << 1)) || !(statusWord & (1 << 2));
            *externalFault = (statusWord & (1 << 3)) || (statusWord & (1 << 4)) || (statusWord & (1 << 5)) || 
                             (statusWord & (1 << 6)) || (statusWord & (1 << 9));
            break;
        case ACTUATOR_MODEL_CTM700:
        case ACTUATOR_MODEL_DANFOSS_FC102:
            /* Status word bit-mapping differs per drive datasheet — not yet implemented */
            break;
        default:
            return false;
    }

    return true;
}

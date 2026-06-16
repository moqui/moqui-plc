#ifndef FIELDBUS_ANALOG_H
#define FIELDBUS_ANALOG_H

#include <stdint.h>
#include <stdbool.h>

#include "ActuatorModel.h"
#include "FieldbusProtocol.h"

/* Math helper */
float scale_value(float value, float min_in, float max_in, float min_out, float max_out);

float processAnalogInput(uint16_t physicalValue, uint16_t minPhysicalValue, uint16_t maxPhysicalValue, 
                         float minValue, float maxValue, float offset, float scalingFactor, int16_t significantDigits);

bool processAnalogOutput(float parameterValue, uint16_t minPhysicalValue, uint16_t maxPhysicalValue, 
                         float minValue, float maxValue, float offset, float scalingFactor, 
                         int16_t significantDigits, bool littleEndian, 
                         uint8_t *byteAnalogOutput, uint16_t *wordAnalogOutput, uint32_t *dWordAnalogOutput);

bool processCyclicInFieldbusData(ActuatorModel model, FieldbusProtocol fieldbus, uint16_t statusWord, 
                                 bool *enabledSensor, bool *disabledSensor, bool *externalFault);

#endif /* FIELDBUS_ANALOG_H */

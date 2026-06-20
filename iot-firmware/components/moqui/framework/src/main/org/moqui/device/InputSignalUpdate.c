#include "InputSignalUpdate.h"

/*
 * InputSignalUpdate — maps physical I/O readings to DeviceFacade fields.
 *
 * In a real application the function signature is extended to receive pointers
 * to the hardware I/O facade and the DeviceFacade:
 *
 *   void InputSignalUpdate_Update(InputSignalUpdate *isu,
 *                                 const IoFacade *io, DeviceFacade *dev)
 *
 * Typical mappings (ESP32 / ESP-IDF):
 *
 *   // ADC — temperature sensor on ADC1 channel 4 (GPIO 32)
 *   int raw = adc1_get_raw(ADC1_CHANNEL_4);
 *   dev->tempFeedback = raw_adc_to_celsius(raw);   // application-specific scaling
 *
 *   // I²C — SHT31 humidity + temperature
 *   sht31_read(&dev->tempFeedback, &dev->rhFeedback);
 *
 *   // GPIO — pump running feedback (NC contact: LOW = running)
 *   dev->coldGlycolPump.enabledSensor  = !gpio_get_level(COLD_PUMP_FB_GPIO);
 *   dev->coldGlycolPump.disabledSensor =  gpio_get_level(COLD_PUMP_FB_GPIO);
 *
 *   // Modbus RTU — duct sensor on slave 3, registers 0x0000..0x0001
 *   dev->ductTempFeedback = modbus_read_float(3, 0x0000);
 *   dev->ductRhFeedback   = modbus_read_float(3, 0x0002);
 *
 * Pattern: io_facade / peripheral -> DeviceFacade fields (pure data flow, no logic).
 */

void InputSignalUpdate_Update(InputSignalUpdate *isu) {
    if (!isu->init) {
        isu->logger.enable = true;
        isu->logger.loggerName = "InputSignalUpdate";
        isu->init = true;
    }

    LOGGER_LOG(&isu->logger, LOG_LEVEL_DEBUG, "Input signals acquisition");

    if (isu->operationType == OPERATING_MODE_INIT) {
        /* Nothing to do — sensors are always live */
    } else if (isu->operationType == OPERATING_MODE_RUN) {
        /* Call application-provided hook if wired */
        if (isu->readInputs && isu->device_facade) {
            isu->readInputs(isu->device_facade);
        }
        /* Extend here: read peripherals -> populate DeviceFacade */
    }
}

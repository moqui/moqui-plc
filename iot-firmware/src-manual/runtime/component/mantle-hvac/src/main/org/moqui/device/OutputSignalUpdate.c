#include "OutputSignalUpdate.h"

/*
 * OutputSignalUpdate — maps DeviceFacade outputs to physical I/O signals.
 *
 * In a real application the function signature is extended to receive pointers
 * to the DeviceFacade and the hardware I/O facade:
 *
 *   void OutputSignalUpdate_Update(OutputSignalUpdate *osu,
 *                                  const DeviceFacade *dev, IoFacade *io)
 *
 * Typical mappings (ESP32 / ESP-IDF):
 *
 *   // GPIO — binary actuator enable outputs
 *   gpio_set_level(COLD_PUMP_ENABLE_GPIO, dev->coldGlycolPump.enable ? 1 : 0);
 *   gpio_set_level(HOT_PUMP_ENABLE_GPIO,  dev->hotGlycolPump.enable  ? 1 : 0);
 *   gpio_set_level(AIR_FLOW_ENABLE_GPIO,  dev->airFlow.enable        ? 1 : 0);
 *
 *   // LEDC PWM — cold glycol valve position (0–100 % -> 0–8191 duty)
 *   uint32_t duty = (uint32_t)(dev->coldGlycolValve.outputActual * 8191.0f / 100.0f);
 *   ledc_set_duty_and_update(LEDC_LOW_SPEED_MODE, COLD_VALVE_CHANNEL, duty, 0);
 *
 *   // DAC — AHU fan speed reference (0–100 % -> 0–3.3 V / 0–255)
 *   uint8_t dac_val = (uint8_t)(dev->ahuFan.outputActual * 255.0f / 100.0f);
 *   dac_output_voltage(DAC_CHANNEL_1, dac_val);
 *
 *   // Modbus RTU — write AHU fan speed setpoint to VFD register
 *   uint16_t vfd_ref = (uint16_t)(dev->ahuFanSpeedSetpoint * 10.0f); // 0.1 Hz units
 *   modbus_write_register(VFD_SLAVE_ID, VFD_SPEED_REG, vfd_ref);
 *
 * Pattern: DeviceFacade fields -> io_facade / peripheral (pure data flow, no logic).
 */

void OutputSignalUpdate_Update(OutputSignalUpdate *osu) {
    if (!osu->init) {
        osu->logger.enable = true;
        osu->logger.loggerName = "OutputSignalUpdate";
        osu->init = true;
    }

    LOGGER_LOG(&osu->logger, LOG_LEVEL_DEBUG, "Output signals actuation");

    if (osu->operationType == OPERATING_MODE_INIT) {
        /* Nothing to do — actuators are driven by Actuator_Update each scan */
    } else if (osu->operationType == OPERATING_MODE_RUN) {
        /* Call application-provided hook if wired */
        if (osu->writeOutputs && osu->device_facade) {
            osu->writeOutputs(osu->device_facade);
        }
        /* Extend here: read DeviceFacade outputs -> drive peripherals */
    }
}

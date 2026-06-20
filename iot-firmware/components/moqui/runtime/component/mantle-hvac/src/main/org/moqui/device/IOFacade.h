#ifndef IO_FACADE_H
#define IO_FACADE_H

#include <stdint.h>

/*
 * IOFacade — physical I/O terminal struct.
 *
 * Port of IOFacade.st.  Naming convention (from ST comments):
 *   deviceName + parameterName + physicalAddress (Modbus channel / address)
 * or
 *   deviceName + parameterName + Min/Max + physicalAddress
 *
 * Physical address syntax: %<area><size><position>
 *   area:  I (input) | Q (output) | M (memory)
 *   size:  X (bit) | B (byte) | W (word) | D (double)
 *
 * Extend with project-specific terminals below the motion examples.
 */
typedef struct {
    /* ===== Physical Input Terminals/Signals ===== */

    /* Motion example — speed/acceleration feedback words */
    uint16_t speedFeedbackSignal[2];
    uint16_t accelerationFeedbackSignal[4];

    /* ===== Physical Output Terminals/Signals ===== */

    /* ABB IO remote device information block */
    uint16_t io1DeviceInformationBlock;
} IOFacade;

#endif /* IO_FACADE_H */

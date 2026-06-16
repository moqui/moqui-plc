#ifndef FIELDBUS_PROTOCOL_H
#define FIELDBUS_PROTOCOL_H

/* Industrial fieldbus protocol identifiers (faithful port of FieldbusProtocol.st). */
typedef enum {
    FIELDBUS_PROTOCOL_MODBUS_TCP,
    FIELDBUS_PROTOCOL_MODBUS_RTU,
    FIELDBUS_PROTOCOL_ETHERNET_IP,
    FIELDBUS_PROTOCOL_PROFINET,
    FIELDBUS_PROTOCOL_CAN_OPEN
} FieldbusProtocol;

#endif /* FIELDBUS_PROTOCOL_H */

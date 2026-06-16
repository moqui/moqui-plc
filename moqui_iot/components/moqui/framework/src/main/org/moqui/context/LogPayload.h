#ifndef LOG_PAYLOAD_H
#define LOG_PAYLOAD_H

#include <stdint.h>

typedef union {
    char message[128];
    uint16_t enumValue;
    double numericValue;
} LogPayload;

#endif /* LOG_PAYLOAD_H */

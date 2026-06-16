#ifndef ENDIAN_UTILS_H
#define ENDIAN_UTILS_H

#include <stdint.h>

uint16_t swapWordEndian(uint16_t value);
uint32_t swapDWordEndian(uint32_t value);
uint64_t swapLWordEndian(uint64_t value);

#endif /* ENDIAN_UTILS_H */

#include "EndianUtils.h"

uint16_t swapWordEndian(uint16_t value) {
    return __builtin_bswap16(value);
}

uint32_t swapDWordEndian(uint32_t value) {
    return __builtin_bswap32(value);
}

uint64_t swapLWordEndian(uint64_t value) {
    return __builtin_bswap64(value);
}

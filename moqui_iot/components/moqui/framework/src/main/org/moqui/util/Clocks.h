#ifndef CLOCKS_H
#define CLOCKS_H

#include <stdbool.h>

typedef struct {
    bool clock10ms;
    bool clock100ms;
    bool clock500ms;  /* ESP32 extension: 500 ms tick — not in IEC 61131-3 Clocks.st */
    bool clock1s;
    bool clock1minute;
} Clocks;

#endif /* CLOCKS_H */

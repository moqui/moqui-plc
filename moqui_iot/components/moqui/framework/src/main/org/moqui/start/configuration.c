#include "configuration.h"
#include "MoquiStart.h"

MoquiStart MoquiStartInstance;
Clocks globalClocks;

void Moqui_Init_Tasks(void) {
    MoquiStartInstance.init   = true;
    MoquiStartInstance.enable = true;
    /* app_main calls this once, then spawns the FreeRTOS task that calls
     * MoquiStart_Update(&MoquiStartInstance, &globalClocks) on every scan. */
}

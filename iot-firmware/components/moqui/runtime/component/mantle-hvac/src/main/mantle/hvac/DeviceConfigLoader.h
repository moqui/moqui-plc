#ifndef DEVICE_CONFIG_LOADER_H
#define DEVICE_CONFIG_LOADER_H

#include "DeviceFacade.h"
#include <stdbool.h>

/*
 * Load a named device configuration from embedded JSON data into a DeviceFacade.
 *
 * configName must match one of the keys registered in DeviceConfigLoader.c.
 * Configurations shipped with the reference HVAC application:
 *   "Phase1HvacCooling"              — cooling phase
 *   "Phase2HvacDrying"               — standard drying
 *   "Phase3HvacHeating"              — heating phase
 *   "Phase4HvacDrying_Progressive"   — progressive drying with RH control
 *   "Phase5HvacDrying_Intensive"     — intensive drying, long cycle
 *   "TestRecipes"                    — test suite configurations
 *
 * Returns true on success, false if the name is unknown or JSON is malformed.
 * On failure dev is left unchanged.
 */
bool DeviceConfigLoader_Load(const char *configName, DeviceFacade *dev);

#endif /* DEVICE_CONFIG_LOADER_H */

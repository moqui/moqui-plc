#ifndef JSON_TO_PARAMETERS_MAPPER_H
#define JSON_TO_PARAMETERS_MAPPER_H

/*
 * JsonToParametersMapper — port of JsonToParametersMapper.st.
 *
 * Application template for applying JSON subscribe values to DeviceFacade.
 * The checked-in implementation performs no writes until an Application-specific
 * mapping is generated from the reviewed DeviceRequestItem whitelist.
 *
 * The .c file retains a disabled mapping table as implementation documentation.
 *
 * Two template entry points:
 *   - Apply()          — non-writing hook for a pre-split key/value
 *   - ParseAndApply()  — parses a flat JSON object and dispatches to Apply()
 */

#include "DeviceFacade.h"
#include <stddef.h>

/* Apply one key/value string pair.  value is the raw JSON token string
 * (e.g. "20.5" for a float, "true"/"false" for a bool, "42" for an int).
 * dev must not be NULL. */
void JsonToParametersMapper_Apply(const char *key, const char *value, DeviceFacade *dev);

/* Parse a flat JSON object string and call Apply() for each key/value pair.
 * json need not be null-terminated if json_len > 0; use json_len=0 for strlen.
 * Handles numeric, boolean, and quoted-string scalar values. */
void JsonToParametersMapper_ParseAndApply(const char *json, int json_len, DeviceFacade *dev);

#endif /* JSON_TO_PARAMETERS_MAPPER_H */

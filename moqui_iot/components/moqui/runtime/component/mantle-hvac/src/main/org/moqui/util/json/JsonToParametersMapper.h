#ifndef JSON_TO_PARAMETERS_MAPPER_H
#define JSON_TO_PARAMETERS_MAPPER_H

/*
 * JsonToParametersMapper — port of JsonToParametersMapper.st.
 *
 * Applies a single key/value pair from a JSON subscribe payload onto the
 * matching DeviceFacade field.  Unknown keys are silently ignored (non-blocking).
 *
 * Adding a new mapping: one line in the s_mappings[] table in the .c file.
 *
 * Two entry points:
 *   - Apply()          — pre-split key + string-value (also used by DeviceConfigLoader)
 *   - ParseAndApply()  — full JSON string (parses then dispatches each pair)
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

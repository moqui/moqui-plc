#ifndef PARAMETERS_TO_JSON_MAPPER_H
#define PARAMETERS_TO_JSON_MAPPER_H

/*
 * ParametersToJsonMapper — descriptor-table driven JSON serializers.
 *
 * Adding a new field to the DeviceFacade telemetry snapshot requires only one
 * additional line in the s_dev_fields[] table inside the .c file.
 * No serializer code needs to change.
 */

#include "Actuator.h"
#include "ProcessPid.h"
#include "DeviceFacade.h"
#include "LogEvent.h"
#include <stddef.h>
#include <stdbool.h>

/* Serialize actuator state into a JSON string.
 * Returns true on success, false if buffer too small or inputs NULL. */
bool serialize_actuator_state(const Actuator *actuator, char *output_buffer, size_t max_len);

/* Serialize the key runtime state of a PID loop.
 * Output: {"sp":<f>,"fb":<f>,"out":<f>,"ovf":<bool>,"lim":<bool>} */
bool serialize_pid_state(const Pid *pid, char *output_buffer, size_t max_len);

/* Serialize a DeviceFacade telemetry snapshot using the descriptor table.
 * Adding a new field: add one entry to s_dev_fields[] in the .c file.
 * Returns true on success. */
bool serialize_device_facade(const DeviceFacade *dev, char *output_buffer, size_t max_len);

/* Serialize a single LogEvent to JSON for MQTT publishing.
 * Returns true on success. */
bool serialize_log_event(const LogEvent *ev, char *output_buffer, size_t max_len);

#endif /* PARAMETERS_TO_JSON_MAPPER_H */

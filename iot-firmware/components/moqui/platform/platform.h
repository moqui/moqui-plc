#ifndef PLATFORM_H
#define PLATFORM_H

/*
 * Platform Abstraction Layer (PAL) — thin interface over platform-specific APIs.
 *
 * Implementations live under platform/<target>/ (e.g. platform/esp32/).
 * To port to STM32, Infineon, or any other FreeRTOS target:
 *   1. Create platform/<target>/ with mqtt_platform.c, net_platform.c, time_platform.c
 *   2. Wire the target in CMakeLists.txt (same pattern as _platform_requires)
 *   3. All framework and runtime code above this layer stays unchanged.
 *
 * Required PAL files per target:
 *   time_platform.c   — pal_time_us()
 *   net_platform.c    — pal_net_is_connected(), pal_net_get_mac_str(), pal_hardware_init()
 *   mqtt_platform.c   — pal_mqtt_*()
 */

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

/* ------------------------------------------------------------------ */
/* System initialisation                                               */
/* ------------------------------------------------------------------ */

/* One-time hardware and middleware init (NVS, netif, event loop on ESP32;
 * BSP/HAL init on other targets).  Must be called once before any other
 * PAL function. */
void pal_hardware_init(void);

/* ------------------------------------------------------------------ */
/* Time                                                                */
/* ------------------------------------------------------------------ */

/* Monotonic microsecond counter since boot (wraps at UINT64_MAX). */
uint64_t pal_time_us(void);

/* ------------------------------------------------------------------ */
/* Network / identity                                                  */
/* ------------------------------------------------------------------ */

/* Returns true if the default network interface is up and reachable. */
bool pal_net_is_connected(void);

/* Writes the device MAC address as a lowercase hex string (no colons)
 * into out[0..max-1], null-terminated.  Example: "a1b2c3d4e5f6". */
void pal_net_get_mac_str(char *out, size_t max);

/* ------------------------------------------------------------------ */
/* MQTT transport                                                      */
/* ------------------------------------------------------------------ */

/* Receive callback — invoked from the MQTT event task context when a
 * subscribed message arrives.  payload is NOT null-terminated; use
 * payload_len.  Implementations must be re-entrant (called from the
 * platform event task, not from the application mqtt_io_task). */
typedef void (*PalMqttRxCb)(const char *topic, int topic_len,
                             const char *payload, int payload_len);

/* Initialise and start the MQTT client.
 * broker_uri: e.g. "mqtt://192.168.1.1:1883".  NULL -> use Kconfig default. */
void pal_mqtt_init(const char *broker_uri);

/* Returns true if the MQTT session is currently connected. */
bool pal_mqtt_is_connected(void);

/* Publish payload (need not be null-terminated if len > 0; pass len=0 to
 * use strlen).  Non-blocking; returns the message-id or -1 on failure. */
int  pal_mqtt_publish(const char *topic, const char *payload, int len, int qos);

/* Subscribe to a topic filter.  Returns msg_id or -1. */
int  pal_mqtt_subscribe(const char *topic, int qos);

/* Register the application-level receive callback (replaces any previous). */
void pal_mqtt_set_rx_cb(PalMqttRxCb cb);

#endif /* PLATFORM_H */

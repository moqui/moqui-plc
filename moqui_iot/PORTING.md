# Porting Guide

All framework and runtime code (`framework/`, `runtime/`) has no platform dependencies and recompiles unchanged on any C99 toolchain.

Porting requires **three new files** and **two small edits**.

---

## Platform Abstraction Layer

```
platform/
├── platform.h          ← contract (8 functions) — do not modify
├── esp32/              ← current implementation (~150 lines total)
│   ├── mqtt_platform.c
│   ├── net_platform.c
│   └── time_platform.c
└── <target>/           ← create this directory
    ├── mqtt_platform.c
    ├── net_platform.c
    └── time_platform.c
```

### Functions to implement

```c
/* time_platform.c */
uint64_t pal_time_us(void);          // monotonic µs counter since boot

/* net_platform.c */
bool pal_net_is_connected(void);     // true if default interface is up
void pal_net_get_mac_str(char *out, size_t max); // MAC as lowercase hex, e.g. "a1b2c3d4e5f6"

/* mqtt_platform.c */
typedef void (*PalMqttRxCb)(const char *topic, int topic_len,
                             const char *payload, int payload_len);
void pal_mqtt_init(const char *broker_uri);
bool pal_mqtt_is_connected(void);
int  pal_mqtt_publish(const char *topic, const char *payload, int len, int qos);
int  pal_mqtt_subscribe(const char *topic, int qos);
void pal_mqtt_set_rx_cb(PalMqttRxCb cb);
```

---

## ESP32-specific touch points outside the PAL

After the portability refactor, the only remaining ESP32 dependencies outside `platform/esp32/` are in `main/main.c`, which is the ESP32 application entry point by definition:

| File | Remaining ESP32 dependency | Notes |
|---|---|---|
| `main/main.c` | `app_main()` entry point | ESP-IDF convention; other targets use `main()` or RTOS init |
| `main/main.c` | `xTaskCreateStaticPinnedToCore` | Dual-core pinning; replace with `xTaskCreateStatic` on single-core targets |
| `mqtt/MqttClient.c` | `freertos/FreeRTOS.h` include path | ESP-IDF puts FreeRTOS headers under `freertos/`; standard FreeRTOS uses bare `FreeRTOS.h` — adjust in CMakeLists.txt |

All other ESP-IDF dependencies have been removed:

- `LoggerFacade.c` — uses `printf` + `pal_time_us()` (no `esp_log.h`)
- `MqttClient.c` — uses `printf` (no `esp_log.h`)
- `main/main.c` — calls `pal_hardware_init()` (no `nvs_flash.h`, `esp_netif.h`, `esp_event.h`)

---

## STM32H7 sketch

Recommended target: **STM32H743** — Cortex-M7 480 MHz, Ethernet MAC (add PHY e.g. LAN8742A), FreeRTOS + lwIP, MISRA-certified HAL.

**`platform/stm32/time_platform.c`**
```c
#include "platform.h"
#include "stm32h7xx_hal.h"
uint64_t pal_time_us(void) { return (uint64_t)HAL_GetTick() * 1000ULL; }
```

**`platform/stm32/net_platform.c`**
```c
#include "platform.h"
#include "lwip/netif.h"
#include <stdio.h>
bool pal_net_is_connected(void) {
    struct netif *n = netif_default;
    return n && netif_is_up(n) && netif_is_link_up(n);
}
void pal_net_get_mac_str(char *out, size_t max) {
    struct netif *n = netif_default;
    if (!n) { snprintf(out, max, "000000000000"); return; }
    snprintf(out, max, "%02x%02x%02x%02x%02x%02x",
             n->hwaddr[0], n->hwaddr[1], n->hwaddr[2],
             n->hwaddr[3], n->hwaddr[4], n->hwaddr[5]);
}
```

**`platform/stm32/mqtt_platform.c`** — use [Eclipse Paho Embedded C](https://github.com/eclipse/paho.mqtt.embedded-c). The pattern is identical to the ESP32 implementation: init client, register event handler, forward to `s_rx_cb`.

**`LoggerFacade.c`** — replace `#include "esp_log.h"` and all `ESP_LOG*` calls with `printf` to UART or `SEGGER_RTT_printf`. Replace `esp_log_timestamp()` with `HAL_GetTick()`.

**`CMakeLists.txt`** — wire `_platform_srcs` for the new target directory, same conditional pattern as the ESP32 block.

---

## Infineon PSoC 6 / XMC

Same three-file approach. PSoC 6 runs FreeRTOS natively; use `mqtt_client` from ModusToolbox or Paho. `pal_time_us` maps to `cyhal_timer_read()` or `Cy_SysTick_GetValue()`.

---

## TI C2000

Not a suitable target for the full stack — no OS, no TCP/IP stack, <256 KB RAM typical. Appropriate only as a **hard real-time co-processor** for the inner PID loop (10 kHz PWM/ADC), communicating with an STM32 or similar running the Moqui stack over SPI or UART.

## TI SimpleLink / Sitara (FreeRTOS-capable)

Modern TI families that *can* run the full moqui-iot stack:

| Family | Representative part | Notes |
|---|---|---|
| **CC3235S/SF** | CC3235SFMODB | Dual-band Wi-Fi MCU, 256 KB RAM, FreeRTOS, built-in MQTT client — closest ESP32 analogue from TI |
| **AM243x** | AM2434 | Quad-core Cortex-R5F, 2 MB SRAM, industrial real-time, FreeRTOS + lwIP + MQTT, EtherCAT capable |
| **AM64x** | AM6442 | Dual A53 (Linux) + dual R5F (FreeRTOS) — run moqui-iot on the R5F cores, Linux SCADA on the A53 |
| **C2000 F28P65x** | TMS320F28P650DK | Newest C2000 with FPU64 + FreeRTOS support; still limited RAM (~1 MB) but viable for the process layer without MQTT |

Porting to **CC3235S** is essentially identical to the ESP32 path — FreeRTOS, lwIP, TI's MQTT client library maps directly to the PAL interface. The three PAL files and `LoggerFacade.c` are the only files that change.

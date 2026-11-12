# iot-firmware

ESP32 implementation of the Moqui PLC framework — a faithful C (MISRA C:2012) port of IEC 61131-3 Structured Text programs.

---

## What it is

The **Moqui IoT framework** allows IEC 61131-3 Structured Text programs (function blocks, state machines, PID controllers, recipe loaders) to run on embedded MCUs with MQTT telemetry. This repository contains the ESP32 port built on ESP-IDF 6.2 and FreeRTOS.

The included HVAC application (`runtime/component/mantle-hvac`) is an example component and a collection of patterns for implementing custom runtime components — it shows how to structure device logic, recipe loading, rule engines, and test suites on top of the framework.

The control task is the sole owner of the application state and logger ring. MQTT callbacks enqueue bounded messages; live writes are applied before the next scan. Physical I/O hooks must be wired for the target board, and network connectivity must be configured by the application.

The framework is designed to be portable. See [PORTING.md](PORTING.md) for STM32, Infineon, and TI targets.

---

## Architecture

```
Core 1 — Control Task (10 ms)        Core 0 — IoT Task
  MoquiStart_Update                     MqttClient_Task
  <application>_Update                    drain pub queue -> broker
  MqttLogAppender_Update

Platform Abstraction Layer (platform/platform.h)
  platform/esp32/  ←  swap to port to another MCU
```

All framework and runtime code sits above the PAL and has no ESP-IDF dependencies.

---

## Prerequisites

- Docker (no local toolchain needed)
- `mosquitto-clients` for the MQTT test (`apt install mosquitto-clients`)
- Docker Compose for the broker test (ships with `moqui-framework`)

---

## Build

```bash
docker run --rm -v "$PWD":/project -w /project espressif/idf:latest \
    /bin/bash -lc "idf.py build"
```

**Clean build artifacts** (files inside the container are owned by root — use Docker to remove them):

```bash
docker run --rm -v "$PWD":/project espressif/idf:latest \
    /bin/bash -lc "rm -rf /project/build /project/sdkconfig /project/sdkconfig.old"
```

---

## Running the test suite (QEMU)

The `HvacTestSuite` validates the framework with 32 functional scenarios. No hardware or network required.

```bash
# 1. Merge binaries into a single QEMU flash image
docker run --rm -v "$PWD":/project -w /project espressif/idf:latest bash -lc "
  cd /project/build &&
  esptool.py --chip=esp32 merge_bin --output=qemu_flash.bin --pad-to-size=4MB \
      --flash-mode dio --flash-freq 40m --flash-size 4MB \
      0x1000 bootloader/bootloader.bin \
      0x8000 partition_table/partition-table.bin \
      0x10000 iot_firmware.bin"

# 2. Run on QEMU
docker run --rm -v "$PWD":/project -w /project espressif/idf:latest bash -lc "
  timeout 60 qemu-system-xtensa -M esp32 -m 4M \
      -drive file=/project/build/qemu_flash.bin,if=mtd,format=raw \
      -global driver=timer.esp32.timg,property=wdt_disable,value=true \
      -nographic 2>&1"
```

Expected output ends with:

```
I (...) HvacTestSuite: All 32 HvacTestSuite scenarios PASSED!
```

---

## Testing the MQTT log pipeline (`moqui-log`)

The firmware path is `LoggerFacade` ring buffer -> `MqttLogAppender` -> MQTT
publish queue -> broker. The gateway receives the canonical map-of-events
envelope, for example:

```json
{"1":{"loggerName":"HVAC_DEMO_PLC","source":"HvacTempSetpoint","type":1,"numericValue":23.5,"uptimeMs":12000,"repeatCount":1}}
```

`loggerName` is the exact owning `Device.deviceId`; empty `source` denotes a
DeviceLog and non-empty `source` an existing `Parameter.parameterId`.
The 29-field ParameterLogger snapshot is retained across ten-event drains.
`uptimeMs` is monotonic time since boot, never an epoch timestamp. In the absence
of an RTC timestamp the receiving gateway assigns the observation date.
Queue saturation is best-effort; inspect `MqttClient_DroppedMessages()` and
`MqttParameterSub.droppedMessages` rather than assuming lossless delivery.

QEMU does not emulate WiFi. `tools/qemu_log_bridge.sh` forwards console **text**
events only, with the same envelope and identity fields. It is not an end-to-end
validation of numeric telemetry or the device MQTT connection. Registered device
identifiers are required for persisted console events.

**1. Start ActiveMQ** — the compose file is in the `moqui-framework` repository:

```bash
# From the moqui-framework docker/ directory
docker compose -f activemq-compose.yml up moqui-broker1 -d
```

**2. Subscribe** (terminal 1):

```bash
mosquitto_sub -h localhost -p 1883 -u artemis -P artemis -t "moqui-log" -W 60
```

**3. Run QEMU through the bridge** (terminal 2):

```bash
docker run --rm --network=host -v "$PWD":/project -w /project espressif/idf:latest bash -lc "
  timeout 30 qemu-system-xtensa -M esp32 -m 4M \
      -drive file=/project/build/qemu_flash.bin,if=mtd,format=raw \
      -global driver=timer.esp32.timg,property=wdt_disable,value=true \
      -nographic 2>&1" | bash tools/qemu_log_bridge.sh localhost 1883
```

The bridge escapes JSON, uses the host reception date and publishes synchronously.
To inspect its output without a broker:

```bash
printf '[I][HVAC_DEMO_PLC] Started\n' | bash tools/qemu_log_bridge.sh --dry-run
```

---

## Debugging in VS Code

The project ships with `.vscode/launch.json` containing three configurations:

| Configuration | When to use |
|---|---|
| **ESP32 GDB Debug** | Host GDB against the compiled ELF |
| **ESP32 LLDB Debug** | macOS / LLVM workflows |
| **Build & Debug ESP32** | Builds first, then attaches Docker-based `xtensa-esp32-elf-gdb` |

**Quick start:**
1. Build (`Ctrl+Shift+B` -> *build:esp32*)
2. Open *Run and Debug* (`Ctrl+Shift+D`), select a configuration, press `F5`
3. Breakpoints: click the gutter; conditional breakpoints: right-click -> *Add Conditional Breakpoint*

Debug controls: `F5` continue · `F10` step over · `F11` step into · `Shift+F11` step out

---

## Kconfig options

| Option | Default | Description |
|---|---|---|
| `MOQUI_MQTT_BROKER_URI` | `mqtt://moqui-device-gateway:1883` | Broker URI |
| `MOQUI_MQTT_DEVICE_TOPIC_PREFIX` | `moqui/device` | Topic prefix; MAC address is appended automatically |
| `MOQUI_CONTROL_TASK_STACK` | 8192 | Core 1 stack (bytes) |
| `IOT_FIRMWARE_TASK_STACK` | 4096 | Core 0 MQTT stack (bytes) |
| `MOQUI_ENABLE_TEST_SUITE` | `y` | Include `HvacTestSuite`; set to `n` for production builds |

---

## Portability

| Target | Status |
|---|---|
| ESP32 (ESP-IDF 6.2) | Production — verified |
| STM32H7 / STM32L4 | Outlined — see [PORTING.md](PORTING.md) |
| Infineon PSoC 6 / XMC | Outlined — see [PORTING.md](PORTING.md) |
| TI C2000 | Out of scope (no OS, no TCP/IP) — see PORTING.md |
| Linux | Not supported — ESP-IDF 6.2 bug in linux target |

## Portable regression checks

From the repository root:

```bash
python3 iot-firmware/tools/test_host.py
ASAN_OPTIONS=detect_leaks=0 python3 iot-firmware/tools/test_host.py --sanitize
python3 -m unittest discover -s scripts/tests -q
```

The host runner compiles the runtime C files and both application entry-point
variants, executes all 32 existing HVAC scenarios and regression cases for scan
ordering, clocks, initialization, multi-recipe progression, JSON bounds, typed
log payloads, command ownership and MQTT fragments. The ESP MQTT tests use API
stubs; they do not replace an ESP-IDF build or board/broker integration tests.
LeakSanitizer may be unavailable in restricted containers; the second command
keeps AddressSanitizer and UndefinedBehaviorSanitizer enabled.

The default FreeRTOS tick must resolve the 10 ms control period. The demo is
best-effort firmware, with no hard-real-time or MISRA certification claim.
A deployable Linux PAL is not provided; use the host runner for portable checks.
The ST bootstrap converter preserves existing C and authoritative `src-manual`
overrides, including support files, even with `--clean`.

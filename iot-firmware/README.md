# iot-firmware

ESP32 implementation of the Moqui PLC framework — a faithful C (MISRA C:2012) port of IEC 61131-3 Structured Text programs.

---

## What it is

The **Moqui IoT framework** allows IEC 61131-3 Structured Text programs (function blocks, state machines, PID controllers, recipe loaders) to run on embedded MCUs with MQTT telemetry. This repository contains the ESP32 port built on ESP-IDF 6.2 and FreeRTOS.

The included HVAC application (`runtime/component/mantle-hvac`) is an example component and a collection of patterns for implementing custom runtime components — it shows how to structure device logic, recipe loading, rule engines, and test suites on top of the framework.

The framework is designed to be portable. See [PORTING.md](PORTING.md) for STM32, Infineon, and TI targets.

---

## Architecture

```
Core 1 — Control Task (100 ms)        Core 0 — IoT Task
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

The `HvacTestSuite` validates the framework with 30 functional scenarios. No hardware or network required.

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
I (...) HvacTestSuite: All 30 HvacTestSuite scenarios PASSED!
```

---

## Testing the MQTT log pipeline (`moqui-log`)

This test exercises the full log path: `LoggerFacade` ring buffer -> `MqttLogAppender` -> broker.

Log persistence uses model identifiers directly. `loggerName` is the exact
owning `Device.deviceId`; an empty `source` produces a `DeviceLog`, while a
non-empty `source` is the exact pre-existing `Parameter.parameterId` and
produces a `ParameterLog`. The HVAC `ParameterLogger` emits the 29 modeled
numeric parameters once per `clock1minute` pulse after `DeviceManager_Update`.
The ring retains a complete snapshot across multiple ten-event MQTT batches.

> QEMU does not emulate WiFi. `tools/qemu_log_bridge.sh` bridges QEMU stdout to the broker by converting each `ESP_LOG` line into a `LogEvent` JSON published via `mosquitto_pub`.

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

Each log line arrives on `moqui-log` as:

```json
{"id":"00000035","logger":"HvacTestSuite","level":2,"marker":0,"ts":2445,"src":"HvacTestSuite","msg":"pass[1]: Init -> Standby","rpt":0}
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

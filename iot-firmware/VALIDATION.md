# IoT port correction validation

Validated on 18 October 2026 against moqui-plc mr-moqui baseline 95fcdf0.

## Corrections

- Production scan is 10 ms, matching ClockGeneration. One task owns the
  application, configuration manager, command application and logger ring.
- MoquiStart invokes the application only in its Run branch, preserves first
  Init after recipe loading, propagates errors and updates physical outputs
  after the application. Application initialization resets signal and air
  distribution state.
- Actuator_Update executes its Init path. Valves follow the persistent pump
  command instead of an enable-request bit consumed as acknowledgment. This
  deliberately corrects the handshake coupling also present in the example ST;
  the canonical ST and Siemens targets are unchanged by this patch.
- The five production recipes are listed and sequenced. Device identities,
  actuator modes, PID scaling/bounds and timing are loaded. TestRecipes is not
  treated as a production recipe. Unsupported config operations fail explicitly.
- MQTT callbacks only enqueue commands; the application applies them between
  scans. Exact topic matching, bounded queues, disable/reconnect generations,
  fragmented payload reassembly and cross-task atomic state prevent the previous
  direct callback writes and truncated/partial commands.
- Live JSON is validated and bounded; nested/unknown envelope fields cannot
  become parameter writes. Non-finite or out-of-range numbers are not applied.
- Logger serialization preserves text/numeric/enum payloads and domain IDs,
  escapes text and publishes the canonical map-of-events envelope. Uptime is
  named uptimeMs; the gateway supplies reception time when no RTC date exists.
- Analog output rejects zero scaling, invalid bounds and unrepresentable
  outputs. Unimplemented drive mappings return unsupported. PID timer addition
  saturates rather than overflowing.
- Static task stacks use configured ESP-IDF byte sizes. Publish retries are
  bounded and dropped-message counters are visible. The build script propagates
  pipeline failures. The old incomplete Linux build reports its missing PAL.
- The bootstrap converter preserves authoritative C overrides and runtime /
  platform support files under --clean. Matching src-manual files are updated.

## Executed checks

- `python3 iot-firmware/tools/test_host.py`: runtime and MQTT PAL regressions,
  actual C implementations, both application entry-point variants, all 32 HVAC
  scenarios. The PAL tests use SDK API stubs.
- `ASAN_OPTIONS=detect_leaks=0 python3 iot-firmware/tools/test_host.py --sanitize`:
  same checks with AddressSanitizer and UndefinedBehaviorSanitizer, passed.
  LeakSanitizer is disabled because this container cannot inspect /proc tasks.
- `python3 -m unittest discover -s scripts/tests -q`: 43 tests passed.
- `python3 -m unittest discover -s .agents/tests -q`: 28 tests passed, with
  moqui-device and moqui-math mr-moqui and moqui-plc4j main checked out alongside.
- Shell syntax, diff whitespace, console bridge JSON/severity/identity checks:
  passed.

## Remaining platform validation

ESP-IDF, Docker, QEMU and an ESP32 board are unavailable in this environment.
An ESP-IDF build and board/broker tests remain necessary, including FreeRTOS tick
resolution, task stack high-water marks, network reconnects and physical I/O.
Board WiFi/Ethernet configuration and physical mappings are application work.
Queue/log overflow is best-effort; this patch does not claim lossless telemetry,
MISRA certification or hard-real-time bounds. The optional peer-PLC parameter
publisher remains disabled until an application-specific mapper is implemented.

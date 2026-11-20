# Complete plan for building a Rust PLC runtime

A plan for a production PLC runtime written in Rust that runs the moqui-plc IEC 61131-3 code on Linux PREEMPT_RT,
built on Intel's Edge Control Libraries for the platform, the kernel, EtherCAT and motion control, and on
moqui-device-gateway for the other field communication.

Status: plan only, for review (2026-11-12). No implementation is authorized yet. This folder keeps its name
(`rust-plc`); renaming it is a later, separate decision.

## 1. Goal and limits

Run the moqui-plc code (`iec61131/`), compiled to native code by RuSTy, as cyclic IEC tasks under the control of
Moqui.

In scope:

- Cyclic IEC tasks of 1 ms and longer, with measured jitter.
- The process image (`%I`, `%Q`, `%M`), RETAIN/PERSISTENT variables, a safe stop.
- The external blocks declared in `interfaces/` (MQTT/JSON/TLS, system, recipes, util) on the moqui-device-gateway
  libraries.
- A multiprotocol `DEVICE_REQUEST` block, the PLC-side equivalent of moqui-device's `run#DeviceRequest`.
- EtherCAT with Intel's IgH master stack and motion control with Intel's RTmotion (PLCopen).
- Control, monitoring and project work from Moqui (Dev AIDE).

Out of scope:

- Functional safety. The runtime is not SIL rated. Safety drives, STO, safety relays and safety PLCs keep that role,
  as `project-architecture.md` of moqui-plc states.
- Xenomai. Intel's libraries support it, but this runtime targets PREEMPT_RT only.
- PROFINET (the Rust stack examined, pnio-rs, is IO-Device only), PROFINET IRT, MRP.
- Online change of a running program without a stop (a later study).
- Certification by PLCopen, ETG or PI.

## 2. Platform constraint: Intel Edge Control Libraries

The runtime is bound to Intel's Edge Control Libraries, as published in
`github.com/open-edge-platform/edge-ai-libraries`, folder `libraries/edge-control-libraries`, pinned at commit
`ac9db63ad548a69d5dbf3b7d3734a5ccb16cec47`. Hardware, kernel, EtherCAT master, servo layer, motion library and
real-time data exchange follow them. A newer commit is taken only after the spikes of section 10 pass on it.

| Component | Intel library | License | Role in the runtime |
|---|---|---|---|
| Real-time kernel | Linux Intel LTS PREEMPT_RT kernel (`linux-intel-rt`) and `eci-customizations` (GRUB entry, deterministic settings), from the ECI repository | Linux: GPL-2.0 | The only supported kernel |
| EtherCAT master | EtherCAT Master Stack (`fieldbus/ethercat-masterstack`): IgH with Intel patches; kernel 5.x/6.x; native drivers for Intel I210/I211 (`igb`), I225/I226 (`igc`) and the integrated GbE of Core 11th/12th gen and Atom x6000 (`dwmac_intel`); multiple masters; a user-space mode (library or daemon, DPDK) | GPL-2.0 (kernel modules), LGPL-2.1 (`libethercat`) | The EtherCAT master, used through its C application interface (`ecrt_*`) |
| EtherCAT configuration | ECAT EnableKit (`fieldbus/ecat-enablekit`): `libecat` (application API), `libeniconfig` (ENI, ETG.2100), `libesiconfig` (ESI, ETG.2000); CoE supported, SoE not | LGPL-2.1 | Network and slave configuration from ENI and ESI files; I/O slaves |
| Servo layer | PLCopen Servo (`plcopen-motion-control/plcopen-servo`): `ecrt_servo`, `ecrt_io`, ENI-driven servo configuration; the bridge between EnableKit and RTmotion | Apache-2.0 | CiA 402 drives as RTmotion axes |
| Motion library | RTmotion (`plcopen-motion-control/plcopen-motion`): C++ PLCopen function blocks, S-curve, Ruckig (v0.9.2) and time-optimal planners, an `Axis` and a `Servo` abstraction | Apache-2.0 | All motion blocks (section 7) |
| Real-time data exchange | Real-time Data Agent (`rt-data-agent/libshm`): block-based lock-free shared-memory ring buffer, one writer and one reader per named buffer | Apache-2.0 | Data from the real-time tasks to the non-real-time processes (telemetry, logs, monitor) |
| Benchmarks | `plcopen-benchmark`, `plcopen-databus` sample applications | Apache-2.0 | Reference measurements and the pattern of real-time to non-real-time communication |

Not used: `fieldbus/robotmctask` (robot control with AI inference) is a reference only.

### 2.1 Hardware and BIOS

Following Intel's system requirements for PLCopen Motion Control:

- CPU: Intel Core Ultra Series 2 or later recommended. Earlier Intel platforms with a supported EtherCAT NIC (Core
  11th and 12th generation, Atom x6000) are acceptable for development and for applications that the timing tests
  of section 10 accept.
- Memory: 16 GB, dual-channel LPDDR5X recommended.
- EtherCAT NIC: an Intel I210/I211 (`igb`), I225/I226 (`igc`) or the integrated GbE (`dwmac_intel`), with Intel's
  native EtherCAT driver. The `generic` driver is for tests only (Intel rates it low performance).
- BIOS: Intel's "Real-time Optimization" settings (hyper-threading off, efficient cores off, `SA GV`, low-power and
  ASPM states off, `Legacy IO Low Latency` on, and the rest of Intel's table).
- One isolated core per real-time domain: the task threads, and each EtherCAT master in user-space library mode.

### 2.2 Operating system

- Ubuntu 22.04 LTS 64-bit (Intel's reference; other Debian-like systems are possible), the ECI APT repository,
  `eci-customizations`, the firmware package, `linux-intel-rt`. Kernel 5.15 or later.
- Real-time validation with `cyclictest` from `rt-tests` v2.6, threads pinned to the isolated cores, as Intel
  prescribes.

### 2.3 Consequences for the rest of the stack

- On a runtime host, EtherCAT is Intel's IgH master. The `ethercat` (ethercrab) backend of moqui-device-gateway is
  not used there: two masters cannot share one NIC, and the IgH master is the one validated with RTmotion.
- The Rust crate `ethercat` (ethercat-rs) binds IgH through its kernel ioctl interface, which Intel's user-space mode
  removes. The runtime binds the C API (`ecrt.h`) itself with `bindgen`, which works in both modes.
- C and C++ libraries under LGPL-2.1 are linked dynamically; Apache-2.0 libraries keep their notices. Whoever owns
  licensing confirms this (decision D6).

## 3. Facts this plan rests on

Checked on 2026-11-12.

| Fact | Source |
|---|---|
| `rust-plc/` holds only ST interface declarations (MQTT/JSON/TLS, system, recipes, util, device tree, PLCopen Motion Part 1 and 4, SoftMotion); no runtime | `rust-plc/README.md` |
| RuSTy has no `CONFIGURATION`/`RESOURCE`/`TASK`; the runtime schedules the tasks | `rust-plc/README.md`, RuSTy parser |
| RuSTy emits a shared object (`--shared --fpic`) and a hardware map (`--hwmap-file=map.json`): each `AT %IX0.0` variable, its generated global (`__PI_0_0`) and address | RuSTy `compiler/plc_driver/src/cli.rs`, `book/technical/outputs/01-hardware-map.md` |
| RuSTy diagnostics have a `clang` format (`file:line:col: severity: message`) | `--error-format=clang` |
| An external block is a `#[repr(C)]` struct, `__vtable` first, plus `extern "C" fn NAME(this: &mut T)` | RuSTy `book/user/interop`, stdlib `timers.rs` |
| moqui-plc type-checks with 17 CODESYS dialect errors left on RuSTy | earlier analysis |
| RuSTy and its stdlib are LGPL-3.0 | RuSTy `Cargo.toml` |
| moqui-device-gateway builds without Moqui (`--no-default-features --features mqtt,opcua,modbus,ethernetip`) and is CC0 | its README |
| RTmotion at the pinned commit has 41 C++ function-block sources: Part 1 motion and administrative blocks (`MC_Power`, `MC_Reset`, `MC_Stop`, `MC_Halt`, `MC_Home`, `MC_MoveAbsolute`, `MC_MoveRelative`, `MC_MoveAdditive`, `MC_MoveVelocity`, `MC_MoveSuperimposed`, `MC_SetPosition`, `MC_SetOverride`, `MC_ReadActual...`, `MC_ReadCommand...`, `MC_ReadStatus`, `MC_ReadMotionState`, `MC_ReadAxisError`, `MC_ReadAxisInfo`, digital I/O blocks), cam and gear blocks (`MC_CamIn`, `MC_CamOut`, `MC_CamTableSelect`, `MC_GearIn`, `MC_GearInPos`, `MC_GearOut`, `MC_DigitalCamSwitch`), `MC_Jog`, `MC_TorqueControl`, `MC_SetControllerMode`; no Part 4 axis-group blocks | `plcopen-motion/library/fb/{public,private}` |
| OpenPLC runtime v4 is GPL-3.0 or commercial: architecture ideas only, no code | `openplc-runtime/LICENSING.md` |
| Dev AIDE (dev instances only) has the workspace with CodeMirror, git and New component from the dev-component template | mr-moqui `runtime/dev-component/dev-aide/README.md` |
| The CodeMirror bundle (`libs/refresh.mjs`, `CODEMIRROR_ENTRY`) exports `StreamLanguage` and `LanguageSupport`, not `completeFromList`; languages are mapped in `js/WebrootCode.js` | mr-moqui `runtime/base-component/webroot/screen/webroot/` |

## 4. Decisions before the first line of code

| # | Decision | Recommendation |
|---|---|---|
| D1 | Folder layout | The runtime goes in `rust-plc/`, beside `interfaces/` (section 6); the folder keeps its name for now |
| D2 | Process model | The runtime is its own process, never inside Moqui: `mlockall` and `SCHED_FIFO` would apply to the whole Moqui server |
| D3 | How the application reaches the runtime | RuSTy builds the application as a shared object, loaded with `dlopen`; a new program needs no new runtime binary. The alternative, one static binary per application, is simpler to validate. Decide after spike S2 |
| D4 | Task configuration | The runtime reads `iec61131/configuration.st` (the subset moqui-plc writes: `TASK` with `INTERVAL` and `PRIORITY`, `PROGRAM ... WITH`). Host facts (cores, NICs, paths) go in `rust-plc.toml` |
| D5 | Field I/O definition | The PLC never reads the Moqui database at run time (moqui-plc rule). Moqui exports `requests.json` and `iomapping.json` from the reviewed model; the EtherCAT network is the ENI file (from the drives' ESI files), as Intel's libraries expect |
| D6 | Licenses | LGPL libraries (RuSTy stdlib, `libethercat`, EnableKit) linked dynamically; Apache-2.0 notices shipped; IgH kernel modules installed as packages. To be confirmed by whoever owns licensing |
| D7 | EtherCAT master mode | **Decided:** start with Intel's IgH kernel module, the most proven of the three modes Intel offers. Spike S7 measures user-space library mode (the master inside the runtime process, one core per master, no ioctl) against it; a switch is a later decision on those numbers. User-space daemon mode (a separate process, at least two cores) is not planned |
| D8 | Control plane between Moqui and the runtime | A local Unix socket for commands (start, stop, status, load); data through Intel's `libshm`; a remote API, if needed, behind authentication. Where the Moqui services live (moqui-device or a new component) is to be decided |
| D9 | RTmotion source | The pinned commit of Intel's repository, built from source with its own CMake; Ruckig at the version RTmotion names (v0.9.2) |
| D10 | PLCopen Part 4 | **Decided:** the axis-group blocks are built on RTmotion's planners and axes (section 7.7), in C++ beside RTmotion and in its style, so that they could be offered to Intel upstream. CODESYS SoftMotion items that moqui-plc uses beyond Part 4 (`SMC_*` types, `MC_GroupPower`, `MC_GroupDisable`) are mapped onto the same implementation where they have a Part 4 meaning; the rest stays out of scope until an application needs it |

## 5. Architecture

```
Moqui (control plane, not real time)              runtime host (Intel platform, linux-intel-rt)
  model -> requests.json, iomapping.json      +-------------------------------------------------------+
  ENI from the drives' ESI files              | watchdog thread           SCHED_FIFO 99   isolated core |
  Dev AIDE: ST editing, build (RuSTy), git    | dispatcher (GCD tick)     SCHED_FIFO 98                 |
  services: load, start, stop, status   <-+-> | task threads              SCHED_FIFO <= 49              |
  monitor, store#Samples, notifications   |   |   copy in -> PROGRAMs (ST, MC blocks)                 |
                                          |   |   -> RTmotion axes -> copy out                        |
                       Unix socket -------+   |   EtherCAT exchange (ecrt_*) in the motion task       |
                       libshm  <--------------| telemetry writers (Intel libshm ring buffers)         |
                                              | comms threads (Tokio, not RT):                        |
                                              |   moqui-device-gateway backends <-> in-process queues |
                                              +-------------------------------------------------------+
                                              IgH EtherCAT master (kernel module, Intel igb/igc/dwmac)
```

Threads and priorities follow OpenPLC v4: the watchdog above everything, the dispatcher above the tasks, the tasks
below 50 so that PREEMPT_RT interrupt threads keep priority. Mutexes a task can take use priority inheritance; state
reads are lock free.

Rules for every real-time path:

- No allocation, no blocking system call, no lock that a non-real-time thread can hold, during a scan.
- A communication block never waits: it posts a request into a wait-free queue and reads the answer on a later scan
  (`Execute`, `Busy`, `Done`, `Error`, as PLCopen blocks do).
- External writes (debug, Moqui setpoints) go into a journal a task applies at the start of its scan.

## 6. Workspace layout

```
moqui-plc/rust-plc/
  interfaces/            ST declarations of the external blocks (exists today)
  PLAN.md                this plan
  Cargo.toml             workspace
  crates/
    plc-rt               scheduler, dispatcher, task threads, RT setup (sched_setattr, affinity, mlockall, clocks)
    plc-image            process image from the RuSTy hardware map, write journal, snapshots
    plc-app              dlopen of the application, PROGRAM entry points, instances, constructors, symbol table
    plc-config           configuration.st subset, rust-plc.toml, requests.json, iomapping.json
    plc-blocks           extern "C" blocks: MQTT/JSON/TLS, DEVICE_REQUEST, system time, recipes, util (PID, RAMP, GEN)
    plc-io               cyclic I/O on the gateway backends (Modbus TCP, EtherNet/IP, OPC UA) into the image
    plc-ethercat-sys     bindgen bindings of IgH ecrt.h and EnableKit libecat
    plc-motion-sys       the C API over RTmotion and PLCopen Servo (C++ shim built from build.rs with CMake)
    plc-motion           the MC_* external blocks, axes, axis groups, CiA 402 servos, ENI loading
                         (the Part 4 group code itself is C++ beside RTmotion, in the motion shim)
    plc-shm              bindings of Intel libshm: telemetry and log ring buffers to non-real-time processes
    plc-retain           RETAIN/PERSISTENT storage (two slots, CRC, written on stop and periodically)
    plc-control          state machine (EMPTY, INIT, RUNNING, STOPPED, ERROR), Unix socket, safe-mode boot
    plc-watchdog         the three watchdog levels, outputs off, fault marker, exit code
  bin/rust-plc           the runtime binary
  third_party/           Intel edge-control-libraries (pinned commit), Ruckig, built by the workspace
  tests/                 unit, fault injection, timing harness
```

moqui-device-gateway is a dependency with `default-features = false` and only the protocol features needed; its
`moqui` and `ethercat` features are never enabled here.

## 7. Main designs

### 7.1 Scheduler

- The dispatcher wakes at the greatest common divisor of the task intervals with `clock_nanosleep(TIMER_ABSTIME)` on
  `CLOCK_MONOTONIC` and releases each task that is due.
- A task: copy in its inputs, apply its journal, call its PROGRAMs in configuration order, copy out its outputs,
  record start, end and overrun.
- A release while the task still runs is counted, not queued; ten consecutive misses stop the PLC in ERROR
  (configurable).
- Statistics per task: execution time and release latency, min, max, mean, percentiles; written to `libshm`.

### 7.2 Faults inside ST code

RuSTy code can divide by zero or index out of bounds. A task traps `SIGFPE` and `SIGSEGV` on its thread and returns
to its recovery point through a small C shim (`sigsetjmp`/`siglongjmp`), since Rust cannot unwind through
`extern "C"` frames. The PLC goes to ERROR naming the task and program. A panic in Rust block code is caught at the
block boundary (`catch_unwind`) and becomes the block's `Error`. C++ exceptions never cross the RTmotion C API
(7.6).

### 7.3 Safe stop and watchdog (three levels)

1. A task stuck for N periods: the dispatcher stops the PLC in ERROR.
2. Every stop: each running scan gets N periods, then is aborted; the journal closes; every `%Q` output goes to 0;
   every RTmotion axis gets `MC_Stop` and its drive is disabled through CiA 402 after standstill; a final I/O and
   EtherCAT cycle sends them; the state is held for a set time.
3. A stalled dispatcher or a stop that does not end: the watchdog writes a fault marker and exits the process with a
   fixed code; systemd restarts the runtime in safe mode, which loads no program, drives the outputs to 0 and
   reports ERROR. The drives' own watchdogs (EtherCAT SM watchdog) are the last resort.

Outputs that must hold a non-zero safe value are configured per output in `iomapping.json`.

### 7.4 Process image

Built at load time from the RuSTy hardware map: each `__PI_*` global is resolved in the loaded object and bound to
its area and offset. plc-io writes inputs and reads outputs only between scans. EtherCAT process data is mapped from
the ENI (slave, PDO entry) to image addresses through `iomapping.json`.

### 7.5 The DEVICE_REQUEST block

```
FUNCTION_BLOCK DEVICE_REQUEST
VAR_INPUT  Execute : BOOL; RequestName : STRING[63]; END_VAR
VAR_OUTPUT Done, Busy, Error : BOOL; ErrorText : STRING[127]; Status : DINT; END_VAR
END_FUNCTION_BLOCK
```

`RequestName` names an entry of `requests.json` (connection, operation, items with address, type and scaling, as
moqui-device holds them). A rising `Execute` posts the request to a comms thread, which runs it on the gateway
facade; values read land in the PLC variables bound to the items at load time; writes take their values at the
rising edge. Polling and subscriptions are plc-io mappers that feed the image every cycle, not this block.

### 7.6 Motion with RTmotion and PLCopen Servo

- RTmotion and PLCopen Servo are C++. The runtime reaches them through a thin C API: one function per MC block call
  and per axis cycle, no exceptions and no C++ types across it, built from `build.rs` with their CMake.
- The ST blocks of `interfaces/plcopen-motion/part1-single-axis.st` become `extern "C"` blocks calling that API.
  Cam, gear, jog, homing and torque blocks, which RTmotion has, are declared in `interfaces/` when an application
  needs them.
- Each axis is an RTmotion axis on a PLCopen Servo `ecrt_servo`, configured from the ENI, for CiA 402 drives on the
  IgH master. Virtual axes serve the tests.
- The motion task: EtherCAT receive, copy in, ST programs with their MC blocks, RTmotion axis cycles, copy out,
  EtherCAT send, all in one scan at the task interval (1 ms in Intel's measurements), Distributed Clocks
  synchronized to the task.
- Before use in the cycle: verify that RTmotion, Ruckig and PLCopen Servo allocate nothing after initialisation
  (allocation counter), and repeat Intel's benchmarks (`plcopen-benchmark`, the multi-axis monitor) on the target.

### 7.7 Axis groups (PLCopen Part 4) on RTmotion

moqui-plc declares 18 Part 4 blocks in `interfaces/plcopen-motion/part4-coordinated.st` and also uses the CODESYS
`MC_GroupPower` and `MC_GroupDisable`. Its code calls `MC_GroupReset`, `MC_GroupPower`, `MC_GroupHalt`,
`MC_GroupStop`, `MC_MoveLinearAbsolute`/`Relative`, `MC_MoveCircularAbsolute`/`Relative`, `MC_SetCoordinateTransform`,
`MC_GroupSetOverride`, `MC_GroupEnable`/`Disable` and the group read blocks; it uses the coordinate systems of
`MC_COORD`. RTmotion has no group blocks, but it has what they need:

- an axis that accepts an external set-point every cycle (`Axis::runCycle(pos, vel)`), the way a group drives its
  member axes;
- a jerk-limited online S-curve planner for one dimension;
- a Ruckig planner for several synchronized axes;
- time-optimal trajectory generation along an N-dimensional path (`Path`, `Trajectory`), which allocates (Eigen,
  `std::list`) and therefore runs only outside the real-time path.

Design:

- **Group object** (`AXES_GROUP_REF`): a fixed set of RTmotion axes, created at load time from the configuration,
  with the Part 4 group state machine (GroupDisabled, GroupStandby, GroupMoving, GroupHoming, GroupStopping,
  GroupErrorStop). The member axes run in external set-point mode while the group moves them and refuse single-axis
  motion blocks meanwhile, as Part 4 requires.
- **Coordinate systems**: ACS (axes), MCS (machine, through the kinematics), PCS (product, through
  `MC_SetCoordinateTransform`). The kinematics is an interface with forward and inverse transforms and the limits of
  its workspace; the first one is the Cartesian gantry (identity). Serial arms (SCARA, six axes) are added per
  application, each with its singularity and reachability checks.
- **`MC_MoveDirectAbsolute`/`Relative`**: point to point in ACS, all axes synchronized and jerk limited with Ruckig.
- **`MC_MoveLinearAbsolute`/`Relative`**: a straight line in MCS or PCS. The path parameter is planned with the
  online S-curve planner under the path's velocity, acceleration and jerk limits; every cycle the pose at that
  parameter goes through the inverse kinematics to the axis set-points, which are checked against each axis' limits.
  A violation stops the group with an error; nothing is clipped silently.
- **`MC_MoveCircularAbsolute`/`Relative`**: an arc defined by the PLCopen circle modes (border point, centre,
  radius), planned the same way along the arc length.
- **Buffer modes**: `Aborting` and `Buffered` first. Blending between segments is a later step, with corner paths
  planned outside the cycle (time-optimal generation with a maximum deviation) and handed to the task as a sampled
  table.
- **Halt, Stop, Override**: a jerk-limited deceleration along the path (the online planner), override as a scale of
  the path velocity.
- **`MC_TrackConveyorBelt`, `MC_TrackRotaryTable`**: a moving PCS driven by a master axis position
  (`setMasterRefPos`/`Vel`, as RTmotion's gearing uses), in a later step of P7.
- Every block runs in the motion task without allocation after initialisation; each planner instance is created
  when the group is created.

Validation: analytical reference lines and arcs on virtual axes, with the path deviation, the velocity,
acceleration and jerk limits and the end positions checked every cycle; then a gantry on real drives.

### 7.8 Data out of the real-time tasks

Telemetry (cycle statistics, variable snapshots, moqui-plc log events when MQTT is not used) leaves the tasks
through Intel `libshm` ring buffers, one writer per task and one reader per consumer, as Intel's Real-time Data
Agent does. The reader is a non-real-time process or thread that forwards the data to Moqui (`store#Samples`,
`store#LogSamples`) or to MQTT. Inside the runtime process, between task threads and Tokio threads, a wait-free
single-producer single-consumer queue is used.

### 7.9 MQTT and the moqui-plc programs

`MQTTClient`, `MQTTPublish`, `MQTTSubscribe`, the JSON builder and reader and the TLS context of
`interfaces/codesys-iiot` are implemented on the gateway MQTT backend, with fixed-size buffers allocated at init.
`LogDispatcher`, `MqttParameterSub` and `ParameterLogger` of moqui-plc then run unchanged, and their messages reach
moqui-device's `store#Samples` and `store#LogSamples` as they do from CODESYS.

## 8. Moqui and Dev AIDE

### 8.1 Structured Text in CodeMirror

1. `refresh.mjs`, `CODEMIRROR_ENTRY`: add `completeFromList` to the `@codemirror/autocomplete` export, then
   `node refresh.mjs --write` (needs the npm packages; it updates `MANIFEST.json` and `NOTICES.md`).
2. `WebrootCode.js`: `st: "st"` and `iecst: "st"` in `EXTENSIONS`, `case "st":` in `languageExtension`, returning one
   cached `LanguageSupport` built with `StreamLanguage`.
3. Tokens: comments `(* *)` and `//`; strings with `$` escapes (`/^'(?:[^'$]|\$.)*'/`); base, typed and time literals
   (`16#FF`, `2#1010`, `INT#5`, `T#1h30m`, `TIME#`, `TOD#`, `DT#`, `D#`); direct addresses (`%IX0.0`, `%QW2`,
   `%MD1`); pragmas (`{external}`, `{attribute ...}`); the IEC keywords including `AT`, `VAR_CONFIG`, `VAR_EXTERNAL`,
   `METHOD`, `INTERFACE`, `CONFIGURATION`, `RESOURCE`, `TASK`, `WITH`, `REF_TO`; types; keyword completion.
4. A linter: a Dev AIDE service runs `plc --check --error-format=clang`, and the editor shows the results through
   `CodeMirror.linter`.

### 8.2 PLC projects in Dev AIDE

- A dev-component template `plc-project`: `iec61131/` sources, `configuration.st`, `rust-plc.toml`, the exported
  `requests.json`, `iomapping.json` and ENI, a README. New component in Dev AIDE creates it; git works as for any
  component.
- Services: build (RuSTy to a shared object and hardware map, diagnostics to the editor), package (application,
  map, JSON and ENI files, checksum, signature), deploy (to a runtime over its control API), start, stop, status.
- A monitor screen: task statistics and variable values from the telemetry; writes through the journal.

Dev AIDE runs code as the server's OS user and loads only on dev instances; a production runtime receives only
signed packages, never code from Dev AIDE directly.

## 9. Phases

Each phase ends with its acceptance criteria met and recorded.

| Phase | Content | Acceptance |
|---|---|---|
| P0 Platform and spikes | Reference Intel host per section 2 (BIOS, Ubuntu, ECI, `linux-intel-rt`), the spikes of section 10 | Each spike's result written down; D3 and D7 decided |
| P1 Runtime core | plc-rt, plc-app, plc-image, plc-control, plc-watchdog, plc-config, plc-shm; no field I/O | 1 ms task, 12 h soak, jitter within the S4 budget; zero allocations in the cycle; stuck task, ST fault and stop tests drive outputs to 0 |
| P2 MQTT blocks | MQTT/JSON/TLS on the gateway; moqui-plc `LogDispatcher`, `MqttParameterSub` | HVAC session end to end: live parameters in, ParameterLog rows out, through Artemis and moqui-device |
| P3 Cyclic I/O and DEVICE_REQUEST | plc-io on Modbus TCP, EtherNet/IP, OPC UA; the block; `requests.json` and `iomapping.json` export from Moqui | Peers driven from ST; broker and device outages do not disturb the cycle |
| P4 Compatibility | retain, system time, recipes, util blocks; the 17 dialect errors resolved | moqui-plc compiles on RuSTy without errors; retain survives a power cut |
| P5 EtherCAT I/O | IgH master and EnableKit from the ENI; EtherCAT I/O slaves in the image; Distributed Clocks | Intel's EnableKit I/O example and our I/O mapping on real slaves at 1 ms; cable pull to a safe stop |
| P6 Motion | RTmotion and PLCopen Servo behind the C API; MC blocks as ST externals; virtual axes, then CiA 402 drives | RTmotion's tests and Intel's benchmarks pass on the target; zero allocations in the cycle; a real axis follows a profile at 1 ms; stop and cable pull end in a safe stop |
| P7 Axis groups | Part 4 on RTmotion (7.7): group object and state machine, Cartesian kinematics, direct, linear and circular moves, halt, stop, override, coordinate transform; then conveyor and rotary-table tracking | Reference paths on virtual axes within the set deviation and limits; moqui-plc axis-group code runs unchanged; a gantry on real drives |
| P8 Moqui and Dev AIDE | ST language, linter, `plc-project` template, build, package, deploy, monitor | A project created, built, deployed and monitored from Dev AIDE |
| P9 Hardening | systemd unit with capabilities, safe-mode boot, signed packages, security review (IEC 62443 basics), documentation | Install from scratch on a clean Intel host; findings closed |

## 10. Spikes (phase P0)

| Spike | Question | Done when |
|---|---|---|
| S1 | RuSTy builds and compiles moqui-plc with `interfaces/` | The error list is known |
| S2 | A PROGRAM as a shared object, loaded with `dlopen`, calling one Rust external block | It runs in a loop; D3 decided |
| S3 | The hardware map resolves `__PI_*` globals in the loaded object | Values move between the image and ST |
| S4 | `cyclictest` (rt-tests v2.6) on the reference host with Intel's BIOS and kernel settings | The cycle and jitter budget is set |
| S5 | Intel `libshm` from Rust in a 1 ms loop, with an allocation counter | No allocation, no missed cycle in 1 h |
| S6 | RTmotion, Ruckig and PLCopen Servo built for PREEMPT_RT; Intel's tests and `plcopen-benchmark` with virtual axes | Results comparable to Intel's published figures |
| S7 | IgH kernel mode and user-space library mode with one EtherCAT slave, `ecrt_*` called from a Rust task thread | Both measured; D7 decided |

## 11. Test strategy

- Unit and property tests for the scheduler arithmetic, the configuration parser, the image binding, the codecs.
- Fault injection: stuck task, ST division by zero and out-of-bounds access, a panicking block, a killed comms
  thread, a full queue, a lost broker, a lost device, a lost EtherCAT slave, a drive fault.
- Timing: `cyclictest` baseline, then the runtime's own statistics under CPU, network and disk load, 12 h minimum.
- An allocation counter around the scan (RuSTy's stdlib has a counting allocator for its tests).
- End to end with the existing peers (Artemis, a Modbus peer, cpppo, the OPC UA test server) and with Moqui.
- Hardware in the loop for EtherCAT and motion before any machine use.

## 12. Risks

| Risk | Mitigation |
|---|---|
| RuSTy maturity: dialect gaps, codegen defects | Spikes first; the CODESYS path stays the reference; issues reported upstream |
| Faults in native ST code | Signal-based recovery per task (7.2), tested in P1 |
| Jitter on the target hardware | S4 sets the budget before any promise; Intel's hardware and BIOS settings only |
| Intel libraries change or move (RTmotion's earlier repository was removed) | Pinned commit; a vendored copy in `third_party/`; upgrades only after the spikes pass |
| C++ in the real-time task | A C API without exceptions, no allocation after start, checked in S6 |
| Part 4 is our own code on RTmotion (D10) | Built in RTmotion's style and tested against analytical paths; kinematics added one at a time, each with singularity and reachability checks; offered to Intel upstream |
| ABI drift between RuSTy versions and the blocks | Pinned RuSTy; headers from `plc_header_generator`; ABI tests in CI |
| LGPL and GPL obligations (RuSTy stdlib, IgH, EnableKit) | D6: dynamic linking, packages, notices |
| Hardware lock-in to Intel | Accepted by decision: the platform is part of the product's validated configuration |
| One-person effort | Phases deliver usable steps: P1 to P3 already replace the CODESYS runtime for applications without EtherCAT |

## 13. Effort

OpenPLC's core is about 8,000 lines of C plus drivers. This runtime reuses moqui-device-gateway for MQTT, Modbus,
EtherNet/IP and OPC UA, and Intel's libraries for EtherCAT, servos and motion: an estimate is 8,000 to 12,000 lines
of Rust plus the C shims, with tests. Validation dominates the effort: timing on the target, fault behaviour, soak
tests, drives. As an order of magnitude for one engineer: P0 to P3 in three to four months; P4 and P5 in two to
three more; P6 two to four months, much less than writing motion control, since RTmotion supplies the planners and
the PLCopen state machines; P7 (axis groups) two to three months for Cartesian kinematics, more for each serial
arm; P8 and P9 one to two months.

## 14. Housekeeping before P0

- Update `.agents/skills/moqui-plant-designer/references/moqui-device-gateway-knowledge.md`: it still describes the
  Quarkus/Camel gateway and its REST endpoints, replaced by the Rust gateway on MR-Moqui.
- Record the decisions of section 4 in a moqui-plc session, as `AGENTS.md` asks.
- If the folder is renamed later, update `scripts/compile-st.py` and the READMEs that name `rust-plc`.

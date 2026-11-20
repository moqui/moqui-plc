# Open-source ST compilers: RuSTy and IronPLC

This is an experimental opening for simple programs and compiler exploration.
RuSTy and IronPLC do not currently provide the complete PLC platform and libraries
required to run moqui-plc. Neither compiling the complete framework nor running
its CODESYS applications is a supported outcome today. Compiler diagnostics below
record the gaps; they are not a claim of a working platform port. The Rust device
gateway (moqui-device-gateway, branch `mr-moqui`) is a component of MR-Moqui that runs
inside the Moqui process; it does not depend on either compiler.

This directory opens the canonical `iec61131/` tree to PLC runtimes built on
open-source compilers, with a Rust runtime as the main target. It contains no
runtime. It contains the **interface declarations** of every external block,
type and function the moqui-plc code uses. `scripts/compile-st.py` uses them to
type-check the code with:

| Target | Compiler | Output | Tested version |
|---|---|---|---|
| `rusty` | [RuSTy](https://github.com/PLC-lang/rusty) (`plc`) | native code via LLVM (object file or shared library) | master `6ffb25ef` |
| `ironplc` | [IronPLC](https://github.com/ironplc/ironplc) (`ironplcc`) | bytecode for the IronPLC VM | 0.249.0 |

IronPLC does not use RuSTy: they are two separate compilers, both written in Rust.

[PLAN.md](PLAN.md) is the complete plan for building a Rust PLC runtime for this code on Linux PREEMPT_RT, on
Intel's Edge Control Libraries (IgH EtherCAT, RTmotion) and moqui-device-gateway. It is a plan only: nothing in it is
implemented yet.

## What compiles and what does not

The moqui-plc code compiles only when every dependency is satisfied.
The CODESYS project gets its dependencies from the CODESYS libraries. On any
other platform they have to be provided by **whoever writes the runtime**:

| Dependency | Interfaces | What the runtime has to implement |
|---|---|---|
| PLCopen Motion Control Part 1 and Part 4 | `interfaces/plcopen-motion/` | `MC_*` function blocks on real axes (for example EtherCAT + CiA 402) |
| CODESYS SoftMotion extensions | `interfaces/codesys-softmotion/` | `SMC_*` types and blocks, kinematics, moving coordinate systems |
| MQTT, JSON, TLS (CODESYS IIoT) | `interfaces/codesys-iiot/` | MQTT 5 client, JSON builder/reader, TLS context |
| Device diagnosis, Ethernet driver, RTC, recipes, atomic add | `interfaces/codesys-system/` | device-tree walk, system clock, recipe file storage, `__XADD` (written `MOQUI_XADD`) for the log buffer counters |
| CODESYS Util | `interfaces/codesys-util/` | `PID`, `RAMP_REAL`, `GEN` |
| Device tree | `interfaces/device-tree/` | the I/O-configuration objects referenced by name (Ethernet adapter, drives, kinematic groups, cam tables) |

The interfaces are **declarations only**. They are written from the PLCopen
interfaces and from the members the moqui-plc code actually uses, with no
vendor code. A clean check means moqui-plc is consistent with these
signatures. It does not make a running PLC: the runtime also has to provide
the scan loop, the task scheduling (RuSTy does not support
`CONFIGURATION`/`RESOURCE`/`TASK`) and the process image.

No OOP is used in the moqui-plc code. Some CODESYS libraries (JSON, recipes,
device diagnosis, SoftMotion coordinate systems) expose methods, so their
interfaces declare `METHOD`s: they mirror the vendor API and are not a
programming model.

## How to use it

### 1. Build the compilers

RuSTy (requires LLVM 21 and Rust):

```bash
git clone https://github.com/PLC-lang/rusty.git
cd rusty && cargo build --release
# compiler:   target/release/plc
# ST stdlib:  libs/stdlib/iec61131-st
```

IronPLC:

```bash
git clone https://github.com/ironplc/ironplc.git
cd ironplc/compiler && cargo build --release
# compiler: target/release/ironplcc
```

### 2. Point the script at the compilers

The defaults are in `scripts/moqui_plc_config.py` (`COMPILE_ST_COMMANDS`,
`RUSTY_STDLIB_ST_ROOT`). Environment variables override them:

```bash
export MOQUI_PLC_RUSTY=~/rusty/target/release/plc
export MOQUI_PLC_RUSTY_STDLIB=~/rusty/libs/stdlib/iec61131-st
export MOQUI_PLC_IRONPLC=~/ironplc/compiler/target/release/ironplcc
```

### 3. Compile

```bash
python3 scripts/compile-st.py --target rusty
python3 scripts/compile-st.py --target ironplc
```

Useful options:

| Option | Effect |
|---|---|
| `--no-interfaces` | compile without the interface declarations (measures the missing dependencies) |
| `--prepare-only` | write the rewritten tree, do not run the compiler |
| `--build` | `rusty`: emit `moqui-plc.o` instead of only checking; the runtime links the interface implementations |
| `--compiler PATH` | compiler executable for this run |
| `--out DIR` | output directory (default `codegen/target/<target>/`) |

Output, under `codegen/target/<target>/` (ignored by git):

- `src/`: the rewritten copy of `iec61131/`;
- `interfaces/`: the interface declarations as passed to the compiler;
- `compiler-output.txt`: raw compiler output;
- `report.json`: every diagnostic, tagged with its origin (`moqui-plc` or `interfaces`).

The summary printed at the end groups the diagnostics by origin and message.

## Dialect rewrites

The canonical tree is CODESYS-flavoured ST. `scripts/st_dialect.py` rewrites
a copy of it, never the tree itself. Only code is rewritten: comments, pragmas
and string literals stay as they are.

| Rewrite | Targets | Why |
|---|---|---|
| `JSON.ERROR` → `JSON_ERROR`, `DED.ERROR` → `DED_ERROR` | both | the two names would collide once namespaces are dropped |
| `MQTT.MQTTClient` → `MQTTClient` (libraries listed in `EXTERNAL_LIBRARY_NAMESPACES`) | both | neither compiler has library namespaces |
| `MQTT.MQTTParam.x` → `x` | both | library parameter lists become globals |
| `ec.init` → `init` (global variable lists) | both | standard ST has no named global variable lists |
| `UNION` → `STRUCT` | both | neither compiler supports `UNION`; member access is unchanged and no caller relies on the memory overlay |
| `__ISVALIDREF(r)` → `(ADR(r) <> 0)` | rusty | CODESYS operator; an unbound reference has address 0 |
| `__UXINT_TO_INT` → `TO_INT` | rusty | CODESYS operator |
| `CONFIGURATION` left out | rusty | task configuration belongs to the runtime |
| nested comments flattened | ironplc | IronPLC does not nest `(* *)` |
| `MainStatus.Idle` → `Idle` | ironplc | IronPLC resolves enumeration values from context and rejects the qualified form in statements |
| `TASK` lines moved before `PROGRAM` lines | ironplc | declaration order required by IronPLC |

The lists of libraries, renames and excluded files are in
`scripts/moqui_plc_config.py`.

## Measured results

Measured on the canonical tree (125 files). RuSTy was built against LLVM 20,
with the two LLVM 21 debug-info calls in `compiler/plc_llvm/src/cpp/llvm_wrapper.cpp`
turned into no-ops; this does not affect type checking.

| | RuSTy without interfaces | RuSTy with interfaces | IronPLC without interfaces | IronPLC with interfaces |
|---|---:|---:|---:|---:|
| errors | 1256 | **17** | 697 | 512 |

### RuSTy: 17 remaining errors, all dialect

Without interfaces, over 90% of the errors come from missing types and their
cascades (every member of an unknown type is unresolved). With the interfaces,
no dependency is missing. The 17 errors left are in 10 files:

| Errors | Cause | Files |
|---:|---|---|
| 14 | generic `TO_*` conversions on non-numeric types (`TO_DINT(TIME)`, `TO_REAL(DWORD)`, `TO_INT(STRING)`): RuSTy limits them to `ANY_NUMBER`; CODESYS also accepts `TIME`, bit strings and strings | `ProcessPid`, `IIRFilter`, `SShapedFunc`, `processAnalogInput`, `doubleWordToReal`, `longWordToLongReal`, `trim` |
| 2 | method call through a pointer (`jsonData^.Clear()`): RuSTy resolves methods only on instances | `SerializeLogToJson`, `SerializeParametersToJson` |
| 1 | `ADR()` of a constant input: RuSTy cannot guarantee read-only use | `MqttConnectionFactory` |

The 155 warnings are informational (`STRING(n)` instead of `STRING[n]`,
`VAR_EXTERNAL` blocks that have no effect in RuSTy, implicit narrowing).

### IronPLC: dialect gaps dominate

IronPLC treats all files as one compilation unit. A file with a syntax error
drops out, and everything that uses it fails with it. Of the 512 errors with
interfaces:

| Errors | Cause |
|---:|---|
| 23 | syntax not accepted, one error in each of 23 files (list below) |
| 260 | cascade: types and instances from the dropped files are unknown |
| 140 | generic `TO_*` conversions (`TO_REAL`, `TO_STRING`, ...) are not available |
| 19 | `VAR_EXTERNAL` without a matching global (cascade) |
| 19 | enumeration values not resolved from context |
| 14 | constants used as type parameters are not resolved |
| 7 | the interface declarations themselves (see below) |
| 30 | other type-check differences |

Syntax IronPLC 0.249 rejects in the codesys dialect:

- `STRING(n)` / `WSTRING(n)` in `VAR_INPUT`, `VAR_EXTERNAL` and global constant lists;
- `REFERENCE TO` in some declarations, and `ref` as an identifier;
- `POINTER TO` in `STRUCT` members, method results and some variable lists;
- `None` as an enumeration value and hexadecimal enumeration values;
- expressions in array bounds (`ARRAY[0..MAX - 1]`);
- `FUNCTION` returning an `ARRAY`;
- several names in one declaration (`a, b : UINT;`);
- an initializer that reads a `VAR_EXTERNAL` constant;
- a method call on a function block output (`trt.cs.GetPose(...)`).

The same constructs in the interface declarations cause the 7 errors listed
under `interfaces`. IronPLC also reports 7 program variables with the same name
as a global: that is a side effect of dropping the qualifier of global variable
lists.

## Findings for the canonical tree

The compilations surfaced issues in the code itself.

1. **Missing `END_FUNCTION_BLOCK`, fixed.** `Filter`, `LevelCtrlStatusMgr`,
   `Axis` and `AxisGroup` had no closing keyword. `export-codesys.py` skipped
   the leading comment up to the first `*)`, so a header comment with a nested
   `(* *)` hid the `FUNCTION_BLOCK` keyword and no closure was added. The
   exporter now skips nested comments, `//` lines, `/* */` blocks and pragmas
   (tests in `scripts/tests/test_export_closure.py`). The four files are
   closed. The SIMATIC AX trees are unchanged: the AX converter already added
   the closure.
2. **`STRUCT(...)` initializer, fixed.** `MqttConnectionFactory` used the
   CODESYS form `STRUCT(psList := ..., udiSize := 5)`. It now uses the standard
   `(psList := ..., udiSize := 5)`, which CODESYS also accepts.
3. **`TIME` resolution, open.** CODESYS `TIME` is a 32-bit count of
   milliseconds; RuSTy `TIME` is a 64-bit count of nanoseconds. Code such as
   `TO_REAL(TO_DINT(tickTime)) / 1000.0` (`IIRFilter`, `ProcessPid`,
   `SShapedFunc`) assumes milliseconds. Even where it compiles, the result on
   RuSTy would be off by a factor of 10^6. A portable form needs an explicit
   unit conversion.
4. **Register-to-float conversion, to verify.** `doubleWordToReal` and
   `longWordToLongReal` assemble the words into a `DWORD`/`LWORD` and then call
   `TO_REAL`/`TO_LREAL`, which converts the **integer value**. It does not
   reinterpret the IEEE-754 bits. If the device sends floating-point registers,
   the result is wrong on every platform, CODESYS included.

## What a Rust runtime adds

This compromise stops at the language boundary. A runtime that wants to host
moqui-plc provides at least:

- a cyclic scheduler with the task configuration of `iec61131/configuration.st`;
- a process image and the I/O drivers (for example EtherCAT with
  [ethercrab](https://github.com/ethercrab-rs/ethercrab));
- the PLCopen motion blocks on CiA 402 drives, with trajectory generation;
- the MQTT, JSON, recipe and clock services behind the interfaces above;
- the device-tree objects declared in `interfaces/device-tree/`.

Once the dialect errors above are resolved, `--build` makes RuSTy emit an object file
whose undefined symbols are these interfaces; the runtime links its implementations.

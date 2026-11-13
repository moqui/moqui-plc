# moqui-plc for CODESYS 4

This folder is the CODESYS 4 project of moqui-plc. The CODESYS 3.5 project is
the archive `../codesys-v3/moqui.projectarchive`.

The application objects are generated from the canonical tree `../iec61131/`,
which stays the source of truth. Change the canonical tree, then regenerate. Do
not edit the generated files by hand.

## Layout

| Path | Content | Generated |
|---|---|---|
| `moqui-plc.fbsws` | workspace | no |
| `moqui-plc.fbsdev/Devices/` | device (CODESYS Virtual Control for Linux SL) and device tree | `busCycleTask` only |
| `moqui-plc.fbsdev/moqui.iecapp` | application `moqui` | no |
| `moqui-plc.fbsdev/moqui.iecapp^/moqui/` | POUs, types and global variable lists | yes |
| `moqui-plc.fbsdev/moqui.iecapp^/TaskConfiguration.json` | tasks of `iec61131/configuration.st` | yes |
| `moqui-plc.fbsdev/moqui.iecapp^/Libraries.json` | library references and placeholder resolutions | yes |
| `moqui-plc.fbsdev/moqui.iecapp^/Libraries.lock.json` | resolved libraries, written by `c4-cli library install` | yes |

The caches and the build output (`.library-cache`, `.compileContexts`,
`.intermediate`, `.bootapp`, `*.fbsws.user`) are ignored by git.

## Generate and build

From the repository root, with CODESYS 4 in `/opt/codesys-4`, or in the folder
named by `MOQUI_PLC_CODESYS4_DIR`:

```sh
# once per machine: install the libraries that CODESYS 4 does not ship
python3 scripts/convert-iec61131-to-codesys4.py --install-libraries

# generate the application, resolve the libraries and compile
python3 scripts/convert-iec61131-to-codesys4.py --build
```

Without options, the script only generates the files. The settings are in the
`CODESYS4_*` section of `scripts/moqui_plc_config.py`.

## From the canonical tree to CODESYS 4

- **Object files.**
  - Each POU, type and global variable list becomes one file in the folder it
    has in the canonical tree.
  - The suffix tells CODESYS 4 the object kind: `.prg.st`, `.fb.st`, `.fn.st`,
    `.struct`, `.enum`, `.union`, `.alias`, `.gvl` or `.itf`. CODESYS 4 ignores
    plain `.st` files.
- **Global variable lists.**
  - A list is a `NAMESPACE` named after it, and its variables are reachable
    only qualified (`ec.dev`, `MoquiConf.brokerUrl`). CODESYS 4 does not
    support `USING`.
  - The generator qualifies every use of a global variable, unless a local
    declaration of the same name hides it, and removes the `VAR_EXTERNAL`
    declarations of global variables.
- **Libraries.**
  - SoftMotion symbols carry their library namespace, as in the CODESYS 3.5
    project.
  - `Util` and `SM3_Robotics` allow unqualified access (`PID`, `RAMP_REAL`,
    `SMC_RCNST`).
- **Device tree.**
  - The objects that CODESYS 3.5 creates from its device tree are declared in
    the list `deviceTree`, generated from
    `rust-plc/interfaces/device-tree/DeviceTree.st`: the drives
    (`AXIS_REF_VIRTUAL_SM3`), the axis groups and the cam table.
  - CODESYS 4 has no SoftMotion device tree, so the drives are virtual.
- **Excluded object.**
  - `NetworkDiagnostics` is left out of the application, together with its
    variable in `MoquiStart` and the `ethernet` adapter.
  - It walks the Ethernet adapter through Device Diagnosis, and CODESYS 4 does
    not generate Device Diagnosis for its device-tree nodes.

## Tasks

`TaskConfiguration.json` lists every task of `iec61131/configuration.st`, with
these active:

- `AxisGroupTestSuiteTask`, which also runs the I/O bus cycle;
- `TestRobotArmPlanningTask`.

The other tasks are commented out (CODESYS 4 accepts comments in its JSON
files). To run one, add it to `CODESYS4_ENABLED_TASKS` in
`scripts/moqui_plc_config.py` and regenerate. If `StartTask` runs, it starts
the framework (`MoquiStart`); `MqttCommunicationTask` runs the MQTT programs
(`MqttParameterSub`, `MqttParameterPub`, `LogDispatcher`).

CODESYS compiles only the POUs reachable from an active task. To check every
POU, regenerate with all tasks of `configuration.st` in `CODESYS4_ENABLED_TASKS`
and compile, then regenerate with the default list.

Intervals are written in microseconds. For example, `T#10ms` becomes `10000`.
This unit is assumed from the `dwInterval` of the CODESYS task configuration.
Check it in the task editor.

## Libraries

CODESYS 4 ships every library of the project except SoftMotion and its
dependencies, and Recipe Management. `--install-libraries` extracts them from
`../codesys-v3/moqui.projectarchive` and installs them into the CODESYS 4
library repository `Default`.

`Libraries.json` resolves the SoftMotion placeholders (`SM3_*`) to the
installed versions. The visualization placeholders stay unresolved, because
moqui-plc has no visualization.

`c4-cli library install` can crash after it has written `Libraries.lock.json`.
`--build` retries it.

## Known limits

- **Axis groups.** `TestRobotArm` and `Tripod` compile, but their kinematics
  is not configured. Configure it before the axis group tests can move the
  robot. The single-axis tests run on the virtual drives.
- **Recipes.** The recipe files (`.txtrecipe`) of the CODESYS 3.5 project are
  not part of this project.

# -*- coding: utf-8 -*-
"""Central configuration for the moqui-plc Python scripts.

Pure data. Import it, do not execute it. It must stay compatible with both
CPython 3 and IronPython 2.7, because export-codesys.py runs inside the CODESYS
script engine. That rules out pyproject.toml (no TOML parser in IronPython 2.7),
f-strings, pathlib and type annotations here.

Scripts under scripts/ import it directly. Skill scripts under .agents/skills/
add <repo>/scripts to sys.path first.
"""
import os

# ---------------------------------------------------------------------------
# Repository paths
# ---------------------------------------------------------------------------

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_ROOT = os.path.join(REPO_ROOT, "scripts")

IEC61131_ROOT = os.path.join(REPO_ROOT, "iec61131")
IEC61131_MOQUI_ROOT = os.path.join(IEC61131_ROOT, "moqui")
IEC61131_FRAMEWORK_ROOT = os.path.join(IEC61131_MOQUI_ROOT, "framework")

SIMATIC_AX_ROOT = os.path.join(REPO_ROOT, "simatic-ax")
IOT_FIRMWARE_ROOT = os.path.join(REPO_ROOT, "iot-firmware")
CODEGEN_ROOT = os.path.join(REPO_ROOT, "codegen")

# export-codesys.py defaults (unchanged values, now in one place)
EXPORT_CODESYS_TARGET_ROOT = os.path.join(REPO_ROOT, "st")
EXPORT_CODESYS_AX_SCRIPT = os.path.join(SCRIPTS_ROOT, "convert-iec61131-to-ax.py")
EXPORT_CODESYS_AX_TARGET_ROOT = SIMATIC_AX_ROOT

# ---------------------------------------------------------------------------
# CODESYS library namespaces <-> vendor-neutral names
# ---------------------------------------------------------------------------
#
# The canonical iec61131 tree uses PLCopen Motion Control names without a
# library qualifier. The CODESYS project uses the SoftMotion libraries, whose
# symbols are qualified with the library namespace (SM3_Basic., SM3_Robotics.).
#
# export-codesys.py strips the qualifier on export (CODESYS -> canonical) and
# scripts/codesys_namespaces.py adds it back (canonical -> CODESYS), for
# example when a generated CODESYS application copies the framework.
#
# Rules:
# - every symbol below appears unqualified in the canonical tree;
# - CODESYS_RENAMED_SYMBOLS maps CODESYS-specific reference types to their
#   PLCopen names; the reverse mapping restores the CODESYS name;
# - spelling is exact (IEC identifiers are case-insensitive, but the mapping
#   keeps each spelling found in the project so the round trip is identical);
# - a qualified symbol missing from this table is left qualified by the export
#   and reported: add it here, then export again.
# - only code is transformed; comments, pragmas and string literals are not.

CODESYS_LIBRARY_SYMBOLS = {
    "SM3_Basic": (
        "AXIS_REF_SM3",
        "MC_AbortTrigger",
        "MC_AccelerationProfile",
        "MC_BUFFER_MODE",
        "MC_CAM_ID",
        "MC_CamIn",
        "MC_CamOut",
        "MC_CamTableSelect",
        "MC_DIRECTION",
        "MC_Direction",
        "MC_GearIn",
        "MC_GearInPos",
        "MC_GearOut",
        "MC_Halt",
        "MC_HaltSuperImposed",
        "MC_Home",
        "MC_Jog",
        "MC_MoveAbsolute",
        "MC_MoveAdditive",
        "MC_MoveRelative",
        "MC_MoveSuperImposed",
        "MC_MoveVelocity",
        "MC_Phasing",
        "MC_PositionProfile",
        "MC_Power",
        "MC_ReadActualPosition",
        "MC_ReadActualTorque",
        "MC_ReadActualVelocity",
        "MC_ReadAxisError",
        "MC_ReadBoolParameter",
        "MC_ReadParameter",
        "MC_ReadStatus",
        "MC_Reset",
        "MC_STARTMODE",
        "MC_SetOverride",
        "MC_SetPosition",
        "MC_Stop",
        "MC_TA_REF",
        "MC_TP_REF",
        "MC_TV_REF",
        "MC_TouchProbe",
        "MC_VelocityProfile",
        "MC_WriteBoolParameter",
        "MC_WriteParameter",
        "TRIGGER_REF",
    ),
    "SM3_Robotics": (
        "AXIS_GROUP_REF_SM3",
        "MC_CIRC_PATHCHOICE",
        "MC_COORD_REF",
        "MC_GroupEnable",
        "MC_GroupHalt",
        "MC_GroupReadActualPosition",
        "MC_GroupReadActualVelocity",
        "MC_GroupReadError",
        "MC_GroupReadStatus",
        "MC_GroupReset",
        "MC_GroupSetOverride",
        "MC_GroupStop",
        "MC_MoveCircularAbsolute",
        "MC_MoveCircularRelative",
        "MC_MoveDirectAbsolute",
        "MC_MoveDirectRelative",
        "MC_MoveLinearAbsolute",
        "MC_MoveLinearRelative",
        "MC_SetCoordinateTransform",
        "MC_TRANSITION_MODE",
        "MC_TrackConveyorBelt",
        "MC_TrackRotaryTable",
        "SMC_CIRC_MODE",
        "SMC_COORD_SYSTEM",
        "SMC_Frame",
        "SMC_Frame_To_CoordRef",
        "SMC_GroupPower",
        "SMC_POS_REF",
    ),
}

# CODESYS name -> canonical (PLCopen) name
CODESYS_RENAMED_SYMBOLS = {
    "AXIS_REF_SM3": "AXIS_REF",
    "AXIS_GROUP_REF_SM3": "AXES_GROUP_REF",
}

# CODESYS extensions with no PLCopen counterpart. They stay unqualified in the
# canonical tree; every other platform must provide them under these names.
CODESYS_VENDOR_EXTENSION_SYMBOLS = (
    "SMC_CIRC_MODE",
    "SMC_COORD_SYSTEM",
    "SMC_Frame",
    "SMC_Frame_To_CoordRef",
    "SMC_GroupPower",
    "SMC_POS_REF",
)

# ---------------------------------------------------------------------------
# compile-st.py: compile the canonical tree with open-source ST compilers
# ---------------------------------------------------------------------------
#
# RuSTy and IronPLC have no CODESYS libraries and no library namespaces.
# compile-st.py copies the canonical tree to codegen/target/<target>/, rewrites
# the CODESYS dialect into the form each compiler accepts, adds the interface
# declarations under rust-plc/interfaces/ and runs the compiler. The canonical
# tree is never modified.

RUST_PLC_ROOT = os.path.join(REPO_ROOT, "rust-plc")
RUST_PLC_INTERFACES_ROOT = os.path.join(RUST_PLC_ROOT, "interfaces")
COMPILE_ST_TARGET_ROOT = os.path.join(CODEGEN_ROOT, "target")

COMPILE_ST_TARGETS = ("rusty", "ironplc")

# Compiler executables. An environment variable overrides each default.
COMPILE_ST_COMMANDS = {
    "rusty": os.environ.get("MOQUI_PLC_RUSTY", "plc"),
    "ironplc": os.environ.get("MOQUI_PLC_IRONPLC", "ironplcc"),
}

# RuSTy declares its standard library in .st headers shipped with the compiler
# (libs/stdlib/iec61131-st in the RuSTy repository). Set the directory here or
# in MOQUI_PLC_RUSTY_STDLIB.
RUSTY_STDLIB_ST_ROOT = os.environ.get("MOQUI_PLC_RUSTY_STDLIB", "")

# CODESYS library namespaces used by the canonical tree. compile-st.py drops
# the qualifier (MQTT.MQTTClient -> MQTTClient); the declarations under
# rust-plc/interfaces/ use the unqualified names.
EXTERNAL_LIBRARY_NAMESPACES = (
    "CAA",
    "DED",
    "IODrvEthernet",
    "JSON",
    "MQTT",
    "NBS",
    "Recipe_Management",
    "SysTimeRtc",
    "Util",
)

# Qualified names that would collide once the namespace is dropped.
EXTERNAL_LIBRARY_RENAMED_SYMBOLS = {
    "JSON.ERROR": "JSON_ERROR",
    "DED.ERROR": "DED_ERROR",
}

# Library parameter lists accessed with a qualifier (MQTT.MQTTParam.x).
EXTERNAL_LIBRARY_PARAMETER_LISTS = (
    "MQTTParam",
)

# Files left out per target, relative to the canonical tree.
# RuSTy has no CONFIGURATION/RESOURCE/TASK: task scheduling belongs to the
# runtime that hosts the compiled code.
COMPILE_ST_EXCLUDED_FILES = {
    "rusty": ("configuration.st",),
    "ironplc": (),
}

# ---------------------------------------------------------------------------
# convert-iec61131-to-codesys4.py: the CODESYS 4 application
# ---------------------------------------------------------------------------
#
# The application of the CODESYS 4 project, relative to the repository root. The generated objects go to
# <application>^/<CODESYS4_SOURCE_FOLDER>/, in the folders of the canonical tree.
CODESYS4_APPLICATION = os.path.join("codesys-v4", "moqui-plc.fbsdev", "moqui.iecapp")
CODESYS4_SOURCE_FOLDER = "moqui"

# Objects of the CODESYS 4 project template that the generated application replaces.
CODESYS4_REMOVED_OBJECTS = ("PROG.prg.st",)

# Canonical objects left out of the CODESYS 4 application, with the variables declared with their type.
# NetworkDiagnostics walks the Ethernet adapter of the device tree through Device Diagnosis, which CODESYS 4 does
# not generate for its device-tree nodes.
CODESYS4_EXCLUDED_OBJECTS = ("NetworkDiagnostics",)

# Tasks of iec61131/configuration.st that run by default. The other tasks stay in TaskConfiguration.json as
# comments: uncomment one to run it.
CODESYS4_ENABLED_TASKS = ("AxisGroupTestSuiteTask", "TestRobotArmPlanningTask")

# The device of the project and the task that runs its I/O bus cycle (an enabled task).
CODESYS4_DEVICE = os.path.join("codesys-v4", "moqui-plc.fbsdev", "Devices", "CODESYS_Virtual_Control_for_Linux_SL.device.json")
CODESYS4_BUS_CYCLE_TASK = "AxisGroupTestSuiteTask"

# The objects that CODESYS 3.5 generates from the device tree (SoftMotion drives, axis groups, cam table) and that
# the code references by name. CODESYS 4 has no SoftMotion device tree: the declarations of the device-tree
# interface become the global variable list deviceTree, with virtual drives, so the application compiles and the
# single-axis tests run without hardware. The axis groups still need their kinematics configured before the
# group tests can run. The Ethernet adapter is left out with NetworkDiagnostics, its only user.
CODESYS4_DEVICE_TREE = os.path.join("rust-plc", "interfaces", "device-tree", "DeviceTree.st")
CODESYS4_DEVICE_TREE_LIST = "deviceTree"
CODESYS4_DEVICE_TREE_EXCLUDED = ("ethernet",)
CODESYS4_DEVICE_TREE_TYPES = {
    "SM3_Basic.AXIS_REF_SM3": "SM3_Basic.AXIS_REF_VIRTUAL_SM3",
    "MC_CAM_REF": "SM3_Basic.MC_CAM_REF",
}

# CODESYS 4 installation and its command line; MOQUI_PLC_C4_CLI overrides the command.
CODESYS4_INSTALL_DIR = os.environ.get("MOQUI_PLC_CODESYS4_DIR", "/opt/codesys-4")
CODESYS4_CLI = os.path.join(CODESYS4_INSTALL_DIR, "c4-cli")

# Library namespace -> managed library, as in the CODESYS 3.5 project. CODESYS 4 ships all of them except
# Recipe Management and SoftMotion, which --install-libraries takes from the CODESYS 3.5 project archive.
CODESYS4_LIBRARIES = {
    "CAA": "CAA Types Extern, 3.5.17 (CAA Technical Workgroup)",
    "JSON": "JSON Utilities SL, 1.13.0 (CODESYS)",
    "MQTT": "MQTT Client SL, 1.13.0 (CODESYS)",
    "NBS": "Net Base Services, 5.0.0 (CODESYS)",
    "Recipe_Management": "Recipe Management, 4.7.0 (System)",
    "SysTimeRtc": "SysTimeRtc, 3.5.22 (System)",
    "Util": "Util, 3.5.22 (System)",
    "SM3_Basic": "SM3_Basic, 4.20.0 (CODESYS)",
    "SM3_Robotics": "SM3_Robotics, 4.20.1 (CODESYS)",
}

# Libraries whose symbols the canonical tree uses without a qualifier and that codesys_namespaces does not
# qualify (Util.PID, Util.RAMP_REAL, SM3_Robotics.SMC_RCNST).
CODESYS4_UNQUALIFIED_LIBRARIES = ("Util", "SM3_Robotics")

# The SoftMotion libraries reach their dependencies through placeholders that, in CODESYS 3.5, the SoftMotion
# package resolves. The visualization placeholders stay unresolved: they are optional and moqui-plc has no
# visualization.
CODESYS4_PLACEHOLDER_OVERRIDES = {
    "SM3_Basic": "SM3_Basic, 4.20.0 (CODESYS)",
    "SM3_CNC": "SM3_CNC, 4.20.0 (CODESYS)",
    "SM3_CPKernelDefaults": "SM3_CPKernelDefaults, 4.19.0 (CODESYS)",
    "SM3_CamBuilder": "SM3_CamBuilder, 4.19.0 (CODESYS)",
    "SM3_CommonPublic": "SM3_CommonPublic, 4.20.0 (CODESYS)",
    "SM3_Drive_CAN": "SM3_Drive_CAN, 4.19.0 (CODESYS)",
    "SM3_Drive_CAN_Brunner": "SM3_Drive_CAN_Brunner, 4.14.0 (3S - Smart Software Solutions GmbH)",
    "SM3_Drive_CAN_DS402_IP": "SM3_Drive_CAN_DS402_IP, 4.19.0 (CODESYS)",
    "SM3_Drive_CiA_DSP402": "SM3_Drive_CiA_DSP402, 4.19.0 (CODESYS)",
    "SM3_Dynamics": "SM3_Dynamics, 4.18.0 (CODESYS)",
    "SM3_Error": "SM3_Error, 4.20.0 (CODESYS)",
    "SM3_Math": "SM3_Math, 4.20.2 (CODESYS)",
    "SM3_RBase": "SM3_RBase, 4.20.0 (CODESYS)",
    "SM3_RCP": "SM3_RCP, 4.20.0 (CODESYS)",
    "SM3_RError": "SM3_RError, 4.18.0 (CODESYS)",
    "SM3_Ramps": "SM3_Ramps, 4.18.0 (CODESYS)",
    "SM3_Robotics": "SM3_Robotics, 4.20.1 (CODESYS)",
    "SM3_Shared": "SM3_Shared, 4.20.0 (CODESYS)",
    "SM3_StringUtils": "SM3_StringUtils, 4.19.0 (CODESYS)",
    "SM3_TrajectoryGeneration": "SM3_TrajectoryGeneration, 4.18.0 (CODESYS)",
    "SM3_Transformation": "SM3_Transformation, 4.20.0 (CODESYS)",
    "TextListUtils": "TextListUtils, 4.7.0 (System)",
}

# --install-libraries: the CODESYS 3.5 project archive the libraries come from, and the CODESYS 4 repository
# (a name from the library repository preferences, or a path) they go to.
CODESYS4_LIBRARY_ARCHIVE = os.path.join("codesys-v3", "moqui.projectarchive")
CODESYS4_LIBRARY_REPOSITORY = "Default"

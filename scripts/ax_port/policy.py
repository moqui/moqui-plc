from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PortPolicy:
    """File selection policy for an AX staging profile."""

    name: str
    include_roots: tuple[Path, ...]
    excluded_relative_paths: frozenset[Path]
    excluded_path_parts: frozenset[str]
    excluded_file_stems: frozenset[str]
    manual_override_stems: frozenset[Path]

    def includes(self, relative_path: Path) -> bool:
        if relative_path.suffix.lower() != ".st":
            return False
        if relative_path in self.excluded_relative_paths:
            return False
        if any(part.lower() in self.excluded_path_parts for part in relative_path.parts):
            return False
        if relative_path.stem.lower() in self.excluded_file_stems:
            return False
        return any(relative_path == root or root in relative_path.parents for root in self.include_roots)


COMMON_EXCLUDED_PATH_PARTS = frozenset({
    "json",
    "mqtt",
    "test",  # Includes Axis/AxisGroup suites, PnP and robot-arm fixtures.
})

COMMON_EXCLUDED_FILE_STEMS = frozenset({
    "mqttparameterpub",
    "mqttparametersub",
})

# Non-Motion overrides: CODESYS implementations replaced by stable, manually maintained AX files.
# Used by all profiles that do not include Motion (process).
PROCESS_MANUAL_OVERRIDE_STEMS = frozenset({
    Path("framework/src/main/org/moqui/context/LoggerFacade"),
    Path("framework/src/main/org/moqui/context/LogRingBuffer"),
    Path("framework/src/main/org/moqui/context/LogSource"),
    Path("framework/src/main/org/moqui/diagnostics/SignalMgmt"),
    Path("framework/src/main/org/moqui/diagnostics/SignalOutputAction"),
    Path("framework/src/main/org/moqui/device/Actuator"),
    Path("framework/src/main/org/moqui/device/ProcessPid"),
    Path("framework/src/main/org/moqui/device/ParseRecipeDInt"),
    Path("framework/src/main/org/moqui/device/ParseRecipeReal"),
    Path("framework/src/main/org/moqui/device/ParseRecipeTime"),
    Path("framework/src/main/org/moqui/device/R_TRIG"),
    Path("framework/src/main/org/moqui/device/DeviceConfigCmds"),
    Path("framework/src/main/org/moqui/device/DeviceConfigMgmt"),
    Path("framework/src/main/org/moqui/device/EdgeTrigStatusMgr"),
    Path("framework/src/main/org/moqui/util/ClockGeneration"),
    Path("framework/src/main/org/moqui/util/IIRFilter"),
    Path("framework/src/main/org/moqui/util/nowTimestamp"),
    Path("framework/src/main/org/moqui/util/SShapedFunc"),
    Path("framework/src/start/MoquiStart"),
    Path("runtime/component/mantle-hvac/src/main/mantle/hvac/Main"),
    Path("runtime/component/mantle-hvac/src/main/mantle/hvac/MainRuleEngine"),
    Path("runtime/component/mantle-hvac/src/main/org/moqui/device/AirDistributionController"),
    Path("runtime/component/mantle-hvac/src/test/HvacTestSuite"),
})

# Motion overrides: adds the two Motion FBs and their compile-only compat stubs.
MOTION_MANUAL_OVERRIDE_STEMS = PROCESS_MANUAL_OVERRIDE_STEMS | frozenset({
    Path("framework/src/main/org/moqui/motion/Axis"),
    Path("framework/src/main/org/moqui/motion/AxisGroup"),
    Path("framework/src/main/org/moqui/motion/AxisMotionCompat"),
    Path("framework/src/main/org/moqui/motion/AxisGroupCompat"),
    Path("framework/src/main/org/moqui/motion/AxisInternalStatus"),
    Path("framework/src/main/org/moqui/motion/AxisGroupInternalStatus"),
    # AX SIMATIC does not allow non-literal array bounds in TYPE definitions.
    # The manual version hardcodes the literal (keep in sync with TRAJECTORY_POINT_LIST_MAX_SIZE).
    Path("framework/src/main/org/moqui/motion/Trajectory"),
})

# Backward-compatible alias: equals the Motion set (superset of all overrides).
MANUAL_AX_OVERRIDE_STEMS = MOTION_MANUAL_OVERRIDE_STEMS

PROCESS_POLICY = PortPolicy(
    name="process",
    include_roots=(
        Path("framework/src/main/org/moqui/context"),
        Path("framework/src/main/org/moqui/device"),
        Path("framework/src/main/org/moqui/diagnostics"),
        Path("framework/src/main/org/moqui/util"),
        Path("framework/src/main/resources/MoquiConf.st"),
        Path("framework/src/start/MoquiStart.st"),
        Path("framework/src/start/MoquiStartStatus.st"),
        Path("runtime/component/mantle-hvac/src/main"),
    ),
    excluded_relative_paths=frozenset({
        Path("framework/src/main/resources/MoquiConf.st"),
        Path("framework/src/main/org/moqui/context/ec.st"),
        Path("runtime/component/mantle-hvac/src/main/org/moqui/device/InputSignalUpdate.st"),
        Path("runtime/component/mantle-hvac/src/main/org/moqui/device/OutputSignalUpdate.st"),
        Path("runtime/component/mantle-hvac/src/main/org/moqui/device/IOFacade.st"),
    }),
    excluded_path_parts=COMMON_EXCLUDED_PATH_PARTS | frozenset({"motion", "opcua"}),
    excluded_file_stems=COMMON_EXCLUDED_FILE_STEMS | frozenset({
        "actuatorgroup",
        "actuatorgroupautochange",
        "actuatorgroupstatus",
        "deserializejsontoparameters",
        "inputsignalupdate",
        "iofacade",
        "jsontoparametersmapper",
        "levelctrlstatusmgr",
        "logdispatcher",
        "parameterstojsonmapper",
        "remoteiomodulediagnostics",
        "serializelogtojson",
        "serializeparameterstojson",
        "signaloutputaction",
        "networkdiagnostics",
    }),
    manual_override_stems=PROCESS_MANUAL_OVERRIDE_STEMS,
)

# Full canonical source coverage, while deliberately excluding unsupported backends,
# all test fixtures/examples, and the two manually maintained Motion FBs.
FULL_POLICY = PortPolicy(
    name="full",
    include_roots=(
        Path("framework/src/main"),
        Path("framework/src/start"),
        Path("runtime/component"),
    ),
    excluded_relative_paths=PROCESS_POLICY.excluded_relative_paths | frozenset({
        Path("framework/src/main/org/moqui/motion/Axis.st"),
        Path("framework/src/main/org/moqui/motion/AxisGroup.st"),
    }),
    excluded_path_parts=COMMON_EXCLUDED_PATH_PARTS | frozenset({
        "opcua",  # Enabled only after the AX OPC UA adapter is available.
    }),
    excluded_file_stems=COMMON_EXCLUDED_FILE_STEMS,
    manual_override_stems=MOTION_MANUAL_OVERRIDE_STEMS,
)

MOTION_POLICY = PortPolicy(
    name="motion",
    include_roots=PROCESS_POLICY.include_roots + (
        Path("framework/src/main/org/moqui/motion"),
    ),
    # Axis and AxisGroup are stable manual AX implementations. The profile stages
    # their public DUT/enum contract but never regenerates the two deterministic FBs.
    excluded_relative_paths=PROCESS_POLICY.excluded_relative_paths | frozenset({
        Path("framework/src/main/org/moqui/motion/Axis.st"),
        Path("framework/src/main/org/moqui/motion/AxisGroup.st"),
    }),
    excluded_path_parts=COMMON_EXCLUDED_PATH_PARTS | frozenset({"opcua"}),
    excluded_file_stems=PROCESS_POLICY.excluded_file_stems,
    manual_override_stems=MOTION_MANUAL_OVERRIDE_STEMS,
)

POLICIES = {policy.name: policy for policy in (PROCESS_POLICY, MOTION_POLICY, FULL_POLICY)}

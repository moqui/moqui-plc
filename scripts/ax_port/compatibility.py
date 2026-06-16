from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CompatibilityResult:
    text: str
    applied: list[str] = field(default_factory=list)


ACTUATOR_REF_DECL_RE = re.compile(r"(?m)^(\s*)ref(\s*:\s*REAL\s*;)")
ACTUATOR_REF_ARG_RE = re.compile(r"(?m)^(\s*)ref(\s*:=)")
MOQUISTART_REMOVABLE_DECL_RE = re.compile(
    r"(?m)^[ \t]*(?:runNetworkDgs\s*:\s*NetworkDiagnostics;|inputProcessing\s*:\s*InputSignalUpdate;|outputProcessing\s*:\s*OutputSignalUpdate;)[ \t]*\n?"
)
WORKEFFORT_DECL_RE = re.compile(r"(?m)^[ \t]*workEffort\s*:\s*WorkEffort;[ \t]*\n?")
EC_NAMESPACE_RE = re.compile(r"\bec\.")
OPERATINGMODE_TYPO_RE = re.compile(r"\boperatingMode(?=[#\.])")

SIGNAL_OUTPUT_ACTION_REPLACEMENTS = {
    "SignalOutputAction#None": "DWORD#16#0000",
    "SignalOutputAction#EmergencyStop": "DWORD#16#0001",
    "SignalOutputAction#ImmediateStop": "DWORD#16#0002",
    "SignalOutputAction#OnPhaseStop": "DWORD#16#0003",
    "SignalOutputAction#Inhibition": "DWORD#16#0004",
    "SignalOutputAction.None": "DWORD#16#0000",
    "SignalOutputAction.EmergencyStop": "DWORD#16#0001",
    "SignalOutputAction.ImmediateStop": "DWORD#16#0002",
    "SignalOutputAction.OnPhaseStop": "DWORD#16#0003",
    "SignalOutputAction.Inhibition": "DWORD#16#0004",
}


def _record(result: CompatibilityResult, name: str, changed: bool) -> None:
    if changed:
        result.applied.append(name)


def apply_file_compatibility(relative: Path, text: str) -> CompatibilityResult:
    """Apply only compatibility rewrites proven necessary by the compiling AX baseline.

    These rules are deliberately separate from syntax conversion because they alter
    identifiers or declarations rather than merely adapting IEC syntax to AX syntax.
    """
    result = CompatibilityResult(text=text)

    if relative.as_posix() == "framework/src/start/MoquiStart.st":
        result.text, count = MOQUISTART_REMOVABLE_DECL_RE.subn("", result.text)
        changed = count > 0
        source = "\t\tenable, init, error, reset : BOOL;"
        target = "\t\tenable, init, error, reset, autoReset : BOOL;"
        if source in result.text:
            result.text = result.text.replace(source, target)
            changed = True
        _record(result, "moqui_start_process_only_declarations", changed)

    if relative.as_posix() == "runtime/component/mantle-hvac/src/main/mantle/hvac/Main.st":
        source = "\t\tdev : DeviceFacade;"
        target = "\t\tclks : Clocks;\n\t\tdev : DeviceFacade;"
        changed = source in result.text and "clks : Clocks;" not in result.text
        if changed:
            result.text = result.text.replace(source, target)
        _record(result, "main_add_ax_clock_facade", changed)

    result.text, count = WORKEFFORT_DECL_RE.subn("", result.text)
    _record(result, "remove_unavailable_work_effort", count > 0)

    result.text, count = EC_NAMESPACE_RE.subn("", result.text)
    _record(result, "remove_ec_namespace", count > 0)

    result.text, count = OPERATINGMODE_TYPO_RE.subn("OperatingMode", result.text)
    _record(result, "normalize_operating_mode_identifier", count > 0)

    signal_changed = False
    for source, target in SIGNAL_OUTPUT_ACTION_REPLACEMENTS.items():
        if source in result.text:
            result.text = result.text.replace(source, target)
            signal_changed = True
    _record(result, "signal_output_action_to_bitmask", signal_changed)

    result.text, decl_count = ACTUATOR_REF_DECL_RE.subn(r"\1referenceValue\2", result.text)
    result.text, arg_count = ACTUATOR_REF_ARG_RE.subn(r"\1referenceValue\2", result.text)
    _record(result, "rename_reserved_ref_identifier", decl_count + arg_count > 0)

    return result

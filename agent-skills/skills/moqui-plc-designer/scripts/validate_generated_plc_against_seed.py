#!/usr/bin/env python3
#
# This software is in the public domain under CC0 1.0 Universal plus a
# Grant of Patent License.
#
# To the extent possible under law, the author(s) have dedicated all
# copyright and related and neighboring rights to this software to the
# public domain worldwide. This software is distributed without any
# warranty.
#
# You should have received a copy of the CC0 Public Domain Dedication
# along with this software (see the LICENSE.md file). If not, see
# <http://creativecommons.org/publicdomain/zero/1.0/>.

from __future__ import annotations

import argparse
from pathlib import Path

from render_device_catalog_from_seed import (
    infer_atomic_kind,
    infer_process_pid_fields,
    load_request_map,
    parse_seed_files,
    parse_statusflow_items,
    render_io_declarations,
    render_parameter_declarations,
    render_state_request_declarations,
    subtree_device_ids,
    validate_seed_graph,
)


def extract_decl_names(block: str) -> list[str]:
    names: list[str] = []
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("(*"):
            continue
        if " : " not in stripped:
            continue
        names.append(stripped.split(" : ", 1)[0])
    return names


def ensure_contains_all(text: str, expected_names: list[str], label: str, errors: list[str]) -> None:
    for name in expected_names:
        if f"{name} :" not in text and f".{name}(" not in text:
            errors.append(f"{label} is missing expected declaration or call for {name}.")


def ensure_no_duplicate_struct_fields(device_facade: str, errors: list[str]) -> None:
    """Catch the class of bug where two independent rendering passes declare
    the same DeviceFacade STRUCT member twice (invalid IEC 61131-3), even if
    a future change reintroduces it through a different code path than the
    one currently deduplicated in render_device_catalog_from_seed.py."""
    seen: dict[str, int] = {}
    for name in extract_decl_names(device_facade):
        seen[name] = seen.get(name, 0) + 1
    duplicates = sorted(name for name, count in seen.items() if count > 1)
    if duplicates:
        errors.append(
            "DeviceFacade.dut declares the same field more than once "
            f"(invalid IEC 61131-3 STRUCT): {', '.join(duplicates)}."
        )


def ensure_process_pid_wiring_matches_inference(
    root_device_id: str,
    devices: dict,
    physical_devices: dict,
    parameters: dict,
    parameter_defs: dict,
    device_manager_text: str,
    errors: list[str],
) -> None:
    """Independently recompute the feedback/setpoint field each ProcessPid
    instance should be wired to, and check the actual generated
    DeviceManager.pou against it. This is a regression guard for
    infer_process_pid_fields(): if that heuristic is ever loosened again
    (e.g. back to a substring match), this check fails even though the two
    functions share the same code path today."""
    for device_id in subtree_device_ids(root_device_id, devices) - {root_device_id}:
        device = devices[device_id]
        if infer_atomic_kind(device) != "ProcessPid":
            continue
        setpoint_field, feedback_field = infer_process_pid_fields(
            root_device_id, device, physical_devices, parameters, parameter_defs
        )
        if feedback_field and f"feedback := dev.{feedback_field}," not in device_manager_text:
            errors.append(
                f"DeviceManager.pou does not wire ProcessPid {device_id}'s feedback input to "
                f"dev.{feedback_field} (the Parameter whose alias/name is exactly 'Feedback')."
            )
        if setpoint_field and f"setpoint := dev.{setpoint_field}," not in device_manager_text:
            errors.append(
                f"DeviceManager.pou does not wire ProcessPid {device_id}'s setpoint input to "
                f"dev.{setpoint_field} (the Parameter whose alias/name is exactly 'Setpoint')."
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Cross-check generated PLC artifacts against Moqui seed data")
    parser.add_argument("xml", nargs="+", type=Path, help="One or more Moqui seed XML files")
    parser.add_argument("--device-id", required=True, help="Root Device ID")
    parser.add_argument("--component-root", type=Path, required=True, help="Generated PLC component root")
    parser.add_argument("--request-map", type=Path, help="Optional JSON file overriding StatusName -> statusNameRequest")
    parser.add_argument(
        "--allow-logical-root",
        action="store_true",
        help="Allow a subsystem DeviceGroup (not a PhysicalDevice) as the Application scope root. "
        "Required for any single-FSM Application whose StatusFlow is attached to a DeviceGroup, "
        "which is the common case produced by render_device_catalog_from_seed.py --allow-logical-root.",
    )
    args = parser.parse_args()

    devices, physical_devices, parameter_defs, parameters, device_requests, request_items, status_items, flow_item_initial = parse_seed_files(args.xml)
    validate_seed_graph(
        args.device_id,
        devices,
        physical_devices,
        parameter_defs,
        parameters,
        device_requests,
        request_items,
        status_items,
        flow_item_initial,
        require_physical_root=not args.allow_logical_root,
    )

    device = devices[args.device_id]
    device_scope = subtree_device_ids(args.device_id, devices)
    analog_decl, digital_decl = render_parameter_declarations(
        args.device_id, device_scope, devices, physical_devices, parameters, parameter_defs
    )
    physical_inputs, physical_outputs = render_io_declarations(
        device_scope, request_items, device_requests, parameter_defs, parameters
    )
    request_map = load_request_map(args.request_map)
    statusflow_items = parse_statusflow_items(device.statusflow_id, status_items, flow_item_initial)
    state_request_declarations = render_state_request_declarations(statusflow_items, request_map)

    device_facade = (args.component_root / "src" / "main" / "org" / "moqui" / "device" / "DeviceFacade.dut").read_text(encoding="utf-8")
    io_facade = (args.component_root / "src" / "main" / "org" / "moqui" / "device" / "IOFacade.dut").read_text(encoding="utf-8")
    device_manager_path = args.component_root / "src" / "main" / "org" / "moqui" / "device" / "DeviceManager.pou"
    device_manager_text = device_manager_path.read_text(encoding="utf-8") if device_manager_path.is_file() else ""
    main_status = (args.component_root / "src" / "main").glob("**/MainStatus.dut")
    main_status_path = next(main_status, None)
    if not main_status_path:
        raise SystemExit("MainStatus.dut not found under generated component root.")
    main_status_text = main_status_path.read_text(encoding="utf-8")

    errors: list[str] = []
    ensure_contains_all(device_facade, extract_decl_names(analog_decl), "DeviceFacade", errors)
    ensure_contains_all(device_facade, extract_decl_names(digital_decl), "DeviceFacade", errors)
    ensure_contains_all(device_facade, extract_decl_names(state_request_declarations), "DeviceFacade", errors)
    ensure_contains_all(io_facade, extract_decl_names(physical_inputs), "IOFacade", errors)
    ensure_contains_all(io_facade, extract_decl_names(physical_outputs), "IOFacade", errors)
    for item in statusflow_items:
        if item.enum_name not in main_status_text:
            errors.append(f"MainStatus.dut is missing enum item {item.enum_name}.")

    ensure_no_duplicate_struct_fields(device_facade, errors)
    if device_manager_text:
        ensure_process_pid_wiring_matches_inference(
            args.device_id, devices, physical_devices, parameters, parameter_defs, device_manager_text, errors
        )
    else:
        errors.append(f"DeviceManager.pou not found under {device_manager_path.parent}.")

    if errors:
        raise SystemExit("Generated PLC cross-check failed:\n- " + "\n- ".join(errors))

    print("Generated PLC cross-check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

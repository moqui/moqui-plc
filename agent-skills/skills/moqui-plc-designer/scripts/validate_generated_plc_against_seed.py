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


def main() -> int:
    parser = argparse.ArgumentParser(description="Cross-check generated PLC artifacts against Moqui seed data")
    parser.add_argument("xml", nargs="+", type=Path, help="One or more Moqui seed XML files")
    parser.add_argument("--device-id", required=True, help="Root Device ID")
    parser.add_argument("--component-root", type=Path, required=True, help="Generated PLC component root")
    parser.add_argument("--request-map", type=Path, help="Optional JSON file overriding StatusName -> statusNameRequest")
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

    if errors:
        raise SystemExit("Generated PLC cross-check failed:\n- " + "\n- ".join(errors))

    print("Generated PLC cross-check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

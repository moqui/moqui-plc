#!/usr/bin/env python3
#
# This software is in the public domain under CC0 1.0 Universal plus a
# Grant of Patent License.
#
# To the extent possible under law, the author(s) have dedicated all
# copyright and related and neighboring rights to this software to the
# public domain worldwide. This software is distributed without any
# warranty.

from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path


PL4J_RUN_SERVICE = "moqui.plc4j.Plc4jServices.run#Plc4jRequest"


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].split(".")[-1]


def load_session(session_dir: Path) -> tuple[Path, dict]:
    session_path = session_dir / "session.json"
    if not session_path.is_file():
        raise SystemExit(f"session.json not found in session directory: {session_dir}")
    return session_path, json.loads(session_path.read_text(encoding="utf-8"))


def find_seed_from_session(session_dir: Path) -> Path:
    session_path, session = load_session(session_dir)
    seed_dir_name = session.get("paths", {}).get("seedDataDir", "seed-data")
    seed_dir = session_path.parent / seed_dir_name
    candidates = []
    for rel_path in session.get("artifacts", {}).get("seedData", []):
        candidate = session_dir / rel_path
        if candidate.is_file():
            candidates.append(candidate)
    if not candidates:
        candidates = sorted(seed_dir.glob("*.xml"))
    if not candidates:
        raise SystemExit(f"No seed XML found in session directory: {session_dir}")
    preferred = [path for path in candidates if "reviewed" in path.name.lower()]
    return preferred[-1] if preferred else candidates[-1]


def resolve_seed(args: argparse.Namespace) -> Path:
    if args.seed:
        return args.seed
    if args.session_dir:
        return find_seed_from_session(args.session_dir)
    raise SystemExit("Provide --seed or --session-dir")


def load_seed(seed_path: Path) -> dict:
    root = ET.parse(seed_path).getroot()
    connections: dict[str, dict] = {}
    requests: dict[str, dict] = {}
    group_members: list[dict] = []
    for elem in root:
        name = local_name(elem.tag)
        attrs = dict(elem.attrib)
        if name == "DeviceConnection":
            connections[attrs["connectionName"]] = attrs
        elif name == "DeviceRequest":
            request_name = attrs.get("requestName") or attrs.get("deviceRequestName")
            if request_name:
                requests[request_name] = attrs
        elif name == "DeviceGroupMember":
            group_members.append(attrs)
    return {
        "connections": connections,
        "requests": requests,
        "group_members": group_members,
    }


def validate_transport_projection(model: dict) -> dict[str, int]:
    requests = model["requests"]
    connections = model["connections"]
    group_members = model["group_members"]

    gateway_requests = []
    plc4j_requests = []
    errors: list[str] = []

    process_plc_ids = {
        member["memberDeviceId"]
        for member in group_members
        if member.get("purposeEnumId") == "DgmpProcessPLC"
    }
    gateway_ids = {
        member["memberDeviceId"]
        for member in group_members
        if member.get("purposeEnumId") == "DgmpEdgeGateway"
    }

    for request_name, request in requests.items():
        router = request.get("routerEnumId", "")
        run_service = request.get("runServiceName", "")
        connection_name = request.get("connectionName", "")

        if router == "DrrMoquiDeviceGateway":
            gateway_requests.append(request_name)
            if request.get("deviceId") not in process_plc_ids:
                errors.append(
                    f"Gateway request {request_name} targets deviceId {request.get('deviceId', '')} that is not modeled as DgmpProcessPLC."
                )

        if run_service == PL4J_RUN_SERVICE:
            plc4j_requests.append(request_name)
            if router != "DrrDirect":
                errors.append(
                    f"PLC4J request {request_name} must use routerEnumId DrrDirect, found {router or '<empty>'}."
                )
            if not connection_name:
                errors.append(f"PLC4J request {request_name} must define connectionName.")
            elif connection_name not in connections:
                errors.append(
                    f"PLC4J request {request_name} references missing DeviceConnection {connection_name}."
                )

    for connection_name, connection in connections.items():
        driver = connection.get("driverEnumId", "")
        transport = connection.get("transportEnumId", "")
        transport_config = connection.get("transportConfig", "")
        if not driver:
            errors.append(f"DeviceConnection {connection_name} must define driverEnumId.")
        if driver != "DcdSimulated" and not transport:
            errors.append(
                f"DeviceConnection {connection_name} with driverEnumId {driver or '<empty>'} must define transportEnumId."
            )
        if not transport_config:
            errors.append(f"DeviceConnection {connection_name} must define transportConfig.")

    if not gateway_requests and not plc4j_requests:
        errors.append(
            "No transport projection found: define at least one gateway-routed request or one PLC4J runServiceName request."
        )
    if gateway_requests and not gateway_ids:
        errors.append(
            "Gateway-routed requests exist but no DeviceGroupMember with purposeEnumId DgmpEdgeGateway was found."
        )

    if errors:
        raise SystemExit("Transport projection validation failed:\n- " + "\n- ".join(errors))

    return {
        "gatewayRequestCount": len(gateway_requests),
        "plc4jRequestCount": len(plc4j_requests),
        "deviceConnectionCount": len(connections),
        "gatewayCount": len(gateway_ids),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate that a seed projects onto at least one transport layer: gateway or PLC4J")
    parser.add_argument("--seed", type=Path, help="Seed XML to inspect")
    parser.add_argument("--session-dir", type=Path, help="Session directory containing seed-data/ and session.json")
    parser.add_argument("--json", action="store_true", help="Print summary as JSON")
    args = parser.parse_args()

    summary = validate_transport_projection(load_seed(resolve_seed(args)))
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print("Transport projection validated.")
        print(f"Gateway requests: {summary['gatewayRequestCount']}")
        print(f"PLC4J requests: {summary['plc4jRequestCount']}")
        print(f"Device connections: {summary['deviceConnectionCount']}")
        print(f"Gateway members: {summary['gatewayCount']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

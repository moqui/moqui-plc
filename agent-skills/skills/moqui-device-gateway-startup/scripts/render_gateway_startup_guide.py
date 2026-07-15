#!/usr/bin/env python3
#
# This software is in the public domain under CC0 1.0 Universal plus a
# Grant of Patent License.
#
# To the extent possible under law, the author(s) have dedicated all
# copyright and related and neighboring rights to this software to the
# public domain worldwide. This software is distributed without any warranty.

from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path


GATEWAY_RUN_SERVICE = "moqui.device.DeviceGatewayServices.run#GatewayDeviceRequest"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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


def resolve_input_seed(args: argparse.Namespace) -> Path:
    if args.seed:
        return args.seed
    if args.session_dir:
        return find_seed_from_session(args.session_dir)
    raise SystemExit("Provide --seed or --session-dir")


def resolve_output_path(args: argparse.Namespace) -> Path:
    if args.output:
        return args.output
    if args.session_dir:
        session_path, session = load_session(args.session_dir)
        config_dir_name = session.get("paths", {}).get("generatedConfigDir", "generated-config")
        return session_path.parent / config_dir_name / "gateway-startup-guide.md"
    raise SystemExit("Provide --output or --session-dir")


def update_session_metadata(session_dir: Path, output_path: Path) -> None:
    session_path, session = load_session(session_dir)
    rel_output = str(output_path.relative_to(session_dir))
    artifacts = session.setdefault("artifacts", {})
    generated_config = artifacts.setdefault("generatedConfig", [])
    if rel_output not in generated_config:
        generated_config.append(rel_output)
    session["updatedAt"] = utc_now()
    session["currentSkill"] = "moqui-device-gateway-startup"
    session_path.write_text(json.dumps(session, indent=2) + "\n", encoding="utf-8")


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].split(".")[-1]


def load_seed_model(seed_path: Path) -> dict:
    tree = ET.parse(seed_path)
    root = tree.getroot()

    devices: dict[str, dict] = {}
    physical_devices: dict[str, dict] = {}
    groups: dict[str, dict] = {}
    group_members: list[dict] = []
    requests: dict[str, dict] = {}
    request_items: list[dict] = []

    for elem in root:
        name = local_name(elem.tag)
        attrs = dict(elem.attrib)
        if name == "Device":
            devices[attrs["deviceId"]] = attrs
        elif name == "PhysicalDevice":
            physical_devices[attrs["deviceId"]] = attrs
        elif name == "DeviceGroup":
            groups[attrs["deviceId"]] = attrs
        elif name == "DeviceGroupMember":
            group_members.append(attrs)
        elif name == "DeviceRequest":
            request_name = attrs.get("requestName") or attrs.get("deviceRequestName")
            if request_name:
                requests[request_name] = attrs
        elif name == "DeviceRequestItem":
            if attrs.get("requestName") or attrs.get("deviceRequestName"):
                request_items.append(attrs)

    request_items_by_name: dict[str, list[dict]] = {}
    for item in request_items:
        request_name = item.get("requestName") or item.get("deviceRequestName")
        if request_name:
            request_items_by_name.setdefault(request_name, []).append(item)

    return {
        "devices": devices,
        "physical_devices": physical_devices,
        "groups": groups,
        "group_members": group_members,
        "requests": requests,
        "request_items_by_name": request_items_by_name,
    }


def analyze_model(model: dict) -> dict:
    devices = model["devices"]
    physical_devices = model["physical_devices"]
    groups = model["groups"]
    group_members = model["group_members"]
    requests = model["requests"]
    request_items_by_name = model["request_items_by_name"]

    memberships_by_device: dict[str, list[dict]] = {}
    for member in group_members:
        memberships_by_device.setdefault(member["memberDeviceId"], []).append(member)

    gateway_ids = sorted(
        {
            member["memberDeviceId"]
            for member in group_members
            if member.get("purposeEnumId") == "DgmpEdgeGateway"
        }
    )

    gateways = []
    blockers: list[str] = []
    warnings: list[str] = []

    if not gateway_ids:
        blockers.append(
            "No gateway was found in DeviceGroupMember with purposeEnumId = DgmpEdgeGateway."
        )

    for gateway_id in gateway_ids:
        gateway_memberships = memberships_by_device.get(gateway_id, [])
        if gateway_id not in devices:
            blockers.append(f"Gateway {gateway_id} is missing its Device row.")
        if gateway_id not in physical_devices:
            blockers.append(f"Gateway {gateway_id} is missing its PhysicalDevice row.")
        if not gateway_memberships:
            blockers.append(f"Gateway {gateway_id} is not assigned to any DeviceGroup.")

        group_ids = sorted({member["deviceId"] for member in gateway_memberships})
        scoped_devices: dict[str, dict] = {}
        for group_id in group_ids:
            for member in group_members:
                if member.get("deviceId") != group_id:
                    continue
                member_id = member.get("memberDeviceId", "")
                purpose = member.get("purposeEnumId", "")
                if member_id == gateway_id:
                    continue
                scoped_devices[member_id] = {
                    "deviceId": member_id,
                    "purposeEnumId": purpose,
                    "groupId": group_id,
                }

        if not scoped_devices:
            blockers.append(f"Gateway {gateway_id} has no in-scope PLC/controller devices in shared groups.")

        scoped_request_names = sorted(
            request_name
            for request_name, request in requests.items()
            if request.get("routerEnumId") == "DrrMoquiDeviceGateway"
            and request.get("deviceId") in scoped_devices
        )
        out_of_scope_request_names = sorted(
            request_name
            for request_name, request in requests.items()
            if request.get("routerEnumId") == "DrrMoquiDeviceGateway"
            and request.get("deviceId")
            and request.get("deviceId") not in scoped_devices
            and request.get("runServiceName") != GATEWAY_RUN_SERVICE
        )
        dispatch_wrappers = sorted(
            (
                request
                for request in requests.values()
                if request.get("deviceId") == gateway_id
                and request.get("runServiceName") == GATEWAY_RUN_SERVICE
            ),
            key=request_name_of,
        )

        if not scoped_request_names:
            warnings.append(
                f"Gateway {gateway_id} has no in-scope DeviceRequest routed through DrrMoquiDeviceGateway."
            )

        gateways.append(
            {
                "gateway_id": gateway_id,
                "group_ids": group_ids,
                "scoped_devices": [scoped_devices[key] for key in sorted(scoped_devices)],
                "requests": [requests[name] for name in scoped_request_names],
                "dispatch_wrappers": dispatch_wrappers,
                "request_items_by_name": request_items_by_name,
                "out_of_scope_request_names": out_of_scope_request_names,
            }
        )

    return {
        "gateways": gateways,
        "blockers": sorted(set(blockers)),
        "warnings": sorted(set(warnings)),
        "all_gateway_requests": [
            request
            for request in requests.values()
            if request.get("routerEnumId") == "DrrMoquiDeviceGateway"
        ],
    }


def classify_request(request: dict) -> str:
    request_type = request.get("requestTypeEnumId", "")
    purpose = request.get("purposeEnumId", "")
    if purpose == "DrpLogging":
        return "PLC log"
    if request_type == "DrtWrite":
        return "Write/control"
    if request_type in {"DrtSubscribe", "DrtCyclic", "DrtEvent", "DrtStateChange"}:
        return "Startup subscription"
    if request_type == "DrtUnsubscribe":
        return "Unsubscribe"
    return request_type or "Unclassified"


def request_name_of(request: dict) -> str:
    return request.get("requestName") or request.get("deviceRequestName") or ""


def render_guide(seed_path: Path, output_path: Path, analysis: dict) -> str:
    lines: list[str] = []
    lines.append("# moqui-device-gateway first-startup guide")
    lines.append("")
    lines.append(f"Source seed: `{seed_path}`")
    lines.append(f"Generated guide: `{output_path}`")
    lines.append("")
    lines.append("This guide is derived from the reviewed seed data. If a prerequisite is wrong, fix the seed/model and regenerate this guide.")
    lines.append("")

    blockers = analysis["blockers"]
    warnings = analysis["warnings"]
    if blockers:
        lines.append("## Startup blockers")
        lines.append("")
        for blocker in blockers:
            lines.append(f"- {blocker}")
        lines.append("")
    if warnings:
        lines.append("## Warnings")
        lines.append("")
        for warning in warnings:
            lines.append(f"- {warning}")
        lines.append("")

    lines.append("## Model preflight")
    lines.append("")
    lines.append("- Verify the reviewed seed has been loaded into the Moqui-managed database used by the gateway.")
    lines.append("- Verify the gateway identity exists as both `Device` and `PhysicalDevice`.")
    lines.append("- Verify the gateway is a `DeviceGroupMember` with `purposeEnumId = DgmpEdgeGateway`.")
    lines.append("- Verify each target PLC/controller is in at least one shared `DeviceGroup` with the gateway.")
    lines.append("- Verify active startup requests use `routerEnumId = DrrMoquiDeviceGateway`.")
    lines.append("")

    for gateway in analysis["gateways"]:
        gateway_id = gateway["gateway_id"]
        lines.append(f"## Gateway `{gateway_id}`")
        lines.append("")
        lines.append("Scope summary:")
        for group_id in gateway["group_ids"]:
            lines.append(f"- DeviceGroup: `{group_id}`")
        if gateway["scoped_devices"]:
            for device in gateway["scoped_devices"]:
                lines.append(
                    f"- In-scope device: `{device['deviceId']}` as `{device['purposeEnumId']}` via group `{device['groupId']}`"
                )
        else:
            lines.append("- No in-scope devices were found.")
        lines.append("")

        lines.append("### Start local dependencies")
        lines.append("")
        lines.append("```bash")
        lines.append("docker compose -f docker/postgres-compose.yml -p moqui-gateway up -d")
        lines.append("docker compose -f ../moqui-framework/docker/activemq-compose.yml -p moqui-gateway up -d")
        lines.append("```")
        lines.append("")

        lines.append("### Build and test the gateway")
        lines.append("")
        lines.append("```bash")
        lines.append("./gradlew clean build")
        lines.append("./gradlew test")
        lines.append("```")
        lines.append("")

        lines.append("### Start the gateway")
        lines.append("")
        lines.append("```bash")
        lines.append(f"GATEWAY_DEVICE_ID={gateway_id} \\")
        lines.append("./gradlew quarkusDev -Dquarkus.profile=local")
        lines.append("```")
        lines.append("")

        lines.append("Equivalent packaged startup:")
        lines.append("")
        lines.append("```bash")
        lines.append(f"GATEWAY_DEVICE_ID={gateway_id} \\")
        lines.append("java -Dquarkus.profile=local -jar build/quarkus-app/quarkus-run.jar")
        lines.append("```")
        lines.append("")

        lines.append("### Readiness check")
        lines.append("")
        lines.append("```bash")
        lines.append("curl http://localhost:8081/q/health/ready")
        lines.append("```")
        lines.append("")

        lines.append("### Modeled DeviceRequest inventory")
        lines.append("")
        if gateway["requests"]:
            for request in gateway["requests"]:
                request_name = request_name_of(request)
                items = gateway["request_items_by_name"].get(request_name, [])
                classification = classify_request(request)
                lines.append(
                    f"- `{request_name}` on `{request.get('deviceId', '')}`: {classification}, type `{request.get('requestTypeEnumId', '')}`, purpose `{request.get('purposeEnumId', '')}`, items `{len(items)}`"
                )
        else:
            lines.append("- No in-scope gateway-routed requests were found.")
        lines.append("")

        if gateway["dispatch_wrappers"]:
            lines.append("### Moqui REST dispatch wrappers")
            lines.append("")
            for request in gateway["dispatch_wrappers"]:
                lines.append(
                    f"- `{request_name_of(request)}` invokes `{request.get('query', '')}` through `{request.get('brokerUri', '')}`."
                )
            lines.append("")

        first_write = next(
            (request for request in gateway["requests"] if request.get("requestTypeEnumId") == "DrtWrite"),
            None,
        )
        if first_write:
            request_name = request_name_of(first_write)
            lines.append("### First manual request")
            lines.append("")
            lines.append("```bash")
            lines.append("curl -X POST \\")
            lines.append(f"  http://localhost:8081/api/device-request/run/{request_name} \\")
            lines.append("  -H 'X-API-Key: change-me'")
            lines.append("```")
            lines.append("")

        log_requests = [request for request in gateway["requests"] if request.get("purposeEnumId") == "DrpLogging"]
        if log_requests:
            lines.append("### PLC log startup note")
            lines.append("")
            for request in log_requests:
                request_name = request_name_of(request)
                lines.append(
                    f"- `{request_name}` is a PLC log request; the MQTT topic must be in `DeviceRequest.query` and `DeviceRequestItem` rows are not required."
                )
            lines.append("")

        live_parameter_requests = [
            request
            for request in gateway["requests"]
            if "live" in request_name_of(request).lower()
        ]
        if live_parameter_requests:
            lines.append("### Live-parameter note")
            lines.append("")
            lines.append(
                "- Confirm that the live-parameter whitelist and MQTT keys used by `MqttParameterSub` are complete before testing parameter writes from Moqui to the PLC."
            )
            lines.append("")

        if gateway["out_of_scope_request_names"]:
            lines.append("### Out-of-scope routed requests")
            lines.append("")
            for request_name in gateway["out_of_scope_request_names"]:
                lines.append(
                    f"- `{request_name}` is routed through `DrrMoquiDeviceGateway` but is outside the scope of gateway `{gateway_id}`."
                )
            lines.append("")

    lines.append("## Useful integration tests from moqui-device-gateway")
    lines.append("")
    lines.append("- `./gradlew test --tests '*GatewaySeededRouteIntegrationTest' -Dquarkus.profile=integration`")
    lines.append("- `./gradlew test --tests '*GatewayDeviceGroupSubscriptionDiscoveryTest' -Dquarkus.profile=integration`")
    lines.append("- `./gradlew test --tests '*PlcLogIngestIntegrationTest' -Dquarkus.profile=integration`")
    lines.append("")

    lines.append("## Principle")
    lines.append("")
    lines.append("The gateway startup procedure must stay a projection of the data model. If startup fails because scope, requests, or identities are incomplete, repair the modeled data and regenerate.")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a model-driven first-startup guide for moqui-device-gateway")
    parser.add_argument("--seed", type=Path, help="Reviewed seed XML to inspect")
    parser.add_argument("--session-dir", type=Path, help="Session directory containing seed-data/ and session.json")
    parser.add_argument("--output", type=Path, help="Output Markdown file")
    args = parser.parse_args()

    seed_path = resolve_input_seed(args)
    output_path = resolve_output_path(args)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    model = load_seed_model(seed_path)
    analysis = analyze_model(model)
    rendered = render_guide(seed_path, output_path, analysis)
    output_path.write_text(rendered, encoding="utf-8")

    if args.session_dir:
        update_session_metadata(args.session_dir, output_path)

    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

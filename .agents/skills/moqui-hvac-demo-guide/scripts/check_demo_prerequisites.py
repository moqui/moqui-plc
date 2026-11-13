#!/usr/bin/env python3
"""Non-mutating prerequisite checks for the local Moqui HVAC demo."""

from __future__ import annotations

import argparse
import json
import shutil
import socket
import subprocess
import sys
from pathlib import Path


REPOSITORIES = (
    "mr-moqui",
    "moqui-device",
    "moqui-math",
    "moqui-device-gateway",
    "moqui-deploy",
    "moqui-plc",
)


def command_path(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    if sys.platform == "win32" and name.startswith("mosquitto_"):
        candidate = Path("C:/Program Files/mosquitto") / f"{name}.exe"
        if candidate.is_file():
            return str(candidate)
    return None


def docker_status(docker: str | None) -> tuple[bool, str]:
    if not docker:
        return False, "docker executable not found"
    try:
        result = subprocess.run(
            [docker, "info", "--format", "{{.ServerVersion}}"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    detail = (result.stdout or result.stderr).strip()
    return result.returncode == 0, detail


def port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def locate_workspace(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    script = Path(__file__).resolve()
    for candidate in (Path.cwd(), *Path.cwd().parents, *script.parents):
        if all((candidate / repo).is_dir() for repo in REPOSITORIES):
            return candidate
    return Path.cwd().resolve()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", help="Directory containing sibling moqui repositories")
    parser.add_argument("--framework-runtime", choices=("rust", "java"), default="rust")
    parser.add_argument("--gateway-runtime", choices=("rust", "quarkus"), default="rust")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args()

    workspace = locate_workspace(args.workspace)
    checks: list[dict[str, object]] = []

    repositories = tuple("moqui-framework" if repo == "mr-moqui" and args.framework_runtime == "java" else repo for repo in REPOSITORIES)
    for repo in repositories:
        path = workspace / repo
        checks.append({"check": f"repository:{repo}", "ok": path.is_dir(), "detail": str(path)})

    required_files = {
        "codesys-project": workspace / "moqui-plc" / "codesys-v3" / "moqui.projectarchive",
        "hvac-seed": workspace / "moqui-device" / "data" / "HVACDemoData.xml",
        "hvac-gateway-demo-data": workspace / "moqui-device" / "data" / "HVACDemoGatewayData.xml",
        "artemis-compose": workspace / "moqui-deploy" / "industrial" / "activemq-compose.yml",
        "postgres-compose": workspace / "moqui-deploy" / "industrial" / "moqui-postgres-compose.yml",
    }
    for name, path in required_files.items():
        checks.append({"check": name, "ok": path.is_file(), "detail": str(path)})

    required_commands = ["docker", "mosquitto_pub", "mosquitto_sub"]
    if args.framework_runtime == "rust" or args.gateway_runtime == "rust":
        required_commands.append("cargo")
    if args.framework_runtime == "java" or args.gateway_runtime == "quarkus":
        required_commands.append("java")
    commands = {name: command_path(name) for name in required_commands}
    for name, path in commands.items():
        checks.append({"check": f"command:{name}", "ok": path is not None, "detail": path or "not found"})

    docker_ok, docker_detail = docker_status(commands["docker"])
    checks.append({"check": "docker-daemon", "ok": docker_ok, "detail": docker_detail})

    # on MR-Moqui the gateway runs inside Moqui (8080); the Quarkus gateway listens on 8081
    gateway_port = (8081, "Quarkus gateway") if args.gateway_runtime == "quarkus" else (8080, "Moqui with the gateway")
    ports = {5432: "PostgreSQL", 1883: "MQTT", gateway_port[0]: gateway_port[1], 8161: "Artemis console"}
    port_state = {str(port): {"service": service, "in_use": port_in_use(port)} for port, service in ports.items()}

    result = {
        "workspace": str(workspace),
        "ready": all(bool(item["ok"]) for item in checks),
        "checks": checks,
        "ports": port_state,
        "note": "Ports already in use are informational; inspect existing demo services before restarting them.",
    }

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Workspace: {workspace}")
        for item in checks:
            marker = "PASS" if item["ok"] else "FAIL"
            print(f"[{marker}] {item['check']}: {item['detail']}")
        for port, state in port_state.items():
            label = "in use" if state["in_use"] else "free"
            print(f"[INFO] port {port} ({state['service']}): {label}")
        print(result["note"])

    return 0 if result["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

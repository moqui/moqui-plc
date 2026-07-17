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
    "moqui-framework",
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
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args()

    workspace = locate_workspace(args.workspace)
    checks: list[dict[str, object]] = []

    for repo in REPOSITORIES:
        path = workspace / repo
        checks.append({"check": f"repository:{repo}", "ok": path.is_dir(), "detail": str(path)})

    required_files = {
        "codesys-project": workspace / "moqui-plc" / "codesys" / "moqui.projectarchive",
        "hvac-seed": workspace / "moqui-device" / "data" / "HVACDemoData.xml",
        "artemis-compose": workspace / "moqui-deploy" / "industrial" / "activemq-compose.yml",
        "postgres-compose": workspace / "moqui-deploy" / "industrial" / "moqui-postgres-compose.yml",
    }
    for name, path in required_files.items():
        checks.append({"check": name, "ok": path.is_file(), "detail": str(path)})

    commands = {name: command_path(name) for name in ("docker", "java", "mosquitto_pub", "mosquitto_sub")}
    for name, path in commands.items():
        checks.append({"check": f"command:{name}", "ok": path is not None, "detail": path or "not found"})

    docker_ok, docker_detail = docker_status(commands["docker"])
    checks.append({"check": "docker-daemon", "ok": docker_ok, "detail": docker_detail})

    ports = {5432: "PostgreSQL", 1883: "MQTT", 8081: "gateway", 8161: "Artemis console"}
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

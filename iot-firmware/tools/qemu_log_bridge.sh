#!/usr/bin/env bash
set -euo pipefail
exec python3 "$(dirname "$0")/qemu_log_bridge.py" "$@"

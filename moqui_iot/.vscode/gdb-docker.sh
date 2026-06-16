#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="$(dirname "$SCRIPT_DIR")"
docker run -i --rm --network host --entrypoint "" -v "$WORKSPACE":"$WORKSPACE" -w "$WORKSPACE" espressif/idf:latest bash -c "source /opt/esp/idf/export.sh >/dev/null 2>&1 && xtensa-esp32-elf-gdb \"\$@\"" -- "$@"

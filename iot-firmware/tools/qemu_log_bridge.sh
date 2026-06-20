#!/usr/bin/env bash
# qemu_log_bridge.sh — pipe QEMU ESP32 stdout through this script to publish
# parsed log lines as LogEvent JSON to the ActiveMQ moqui-log MQTT topic.
#
# Usage:
#   <qemu-command> 2>&1 | bash tools/qemu_log_bridge.sh [broker_host] [broker_port]
#
# Defaults: broker=localhost, port=1883, user=artemis, password=artemis
#
# LogEvent JSON format mirrors LoggerFacade ring buffer entries:
#   {"id":"<seq>","logger":"<tag>","level":<n>,"marker":0,
#    "ts":<esp_ms>,"src":"<tag>","msg":"<message>","rpt":0}
#
# Level mapping (ESP_LOG -> LogLevel enum):
#   E=5(FATAL) W=4(WARN) I=2(INFO) D=1(DEBUG) V=0(TRACE)

BROKER="${1:-localhost}"
PORT="${2:-1883}"
TOPIC="moqui-log"
USER="artemis"
PASS="artemis"

seq=0
declare -A level_map=( [E]=5 [W]=4 [I]=2 [D]=1 [V]=0 )

echo "[bridge] Publishing to mqtt://${BROKER}:${PORT}/${TOPIC}" >&2

while IFS= read -r line; do
    # Forward raw line to terminal
    echo "$line"

    # Match ESP_LOG pattern: "I (12345) TAG: message"
    if [[ "$line" =~ ^([EWDVI])\ \(([0-9]+)\)\ ([^:]+):\ (.*)$ ]]; then
        lvl_char="${BASH_REMATCH[1]}"
        ts="${BASH_REMATCH[2]}"
        tag="${BASH_REMATCH[3]}"
        msg="${BASH_REMATCH[4]}"
        # strip trailing whitespace / carriage return
        msg="${msg%$'\r'}"
        tag="${tag%% }"

        level="${level_map[$lvl_char]:-2}"
        seq=$((seq + 1))
        id=$(printf "%08x" "$seq")

        # Escape double quotes in message and tag for JSON
        msg="${msg//\"/\\\"}"
        tag="${tag//\"/\\\"}"

        json="{\"id\":\"${id}\",\"logger\":\"${tag}\",\"level\":${level},\"marker\":0,\"ts\":${ts},\"src\":\"${tag}\",\"msg\":\"${msg}\",\"rpt\":0}"

        mosquitto_pub -h "$BROKER" -p "$PORT" \
            -u "$USER" -P "$PASS" \
            -t "$TOPIC" -m "$json" &
    fi
done

wait
echo "[bridge] Done. Published ${seq} log events." >&2

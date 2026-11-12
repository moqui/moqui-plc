#!/usr/bin/env python3
"""Forward QEMU text diagnostics as canonical LoggerFacade batches.

This exercises text logging only. Numeric ring-buffer telemetry requires the
firmware MQTT transport; console output is not a substitute for that test.
"""
import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import subprocess
import sys

LEVELS = {'V': 0, 'D': 1, 'I': 2, 'W': 3, 'E': 4}
PATTERNS = (re.compile(r'^([EWDVI]) \((\d+)\) ([^:]+): (.*)$'),
            re.compile(r'^\[([EWDVI])\]\[([^]]+)\] (.*)$'))

def encode(line, sequence):
    match = PATTERNS[0].match(line)
    if match:
        level, uptime, logger, message = match.groups()
    else:
        match = PATTERNS[1].match(line)
        if not match:
            return None
        level, logger, message = match.groups()
        uptime = None
    event = {'loggerName': logger.strip(), 'source': '', 'type': 0,
             'level': LEVELS[level], 'marker': 0, 'message': message,
             'repeatCount': 1, 'logEventId': f'{sequence:08x}',
             'logEventDate': datetime.now().strftime('DT#%Y-%m-%d-%H:%M:%S')}
    if uptime is not None:
        event['uptimeMs'] = int(uptime)
    return json.dumps({'1': event}, ensure_ascii=False)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('host', nargs='?', default='localhost')
    parser.add_argument('port', nargs='?', default='1883')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    count = 0
    for line in sys.stdin:
        line = line.rstrip('\r\n')
        payload = encode(line, count + 1)
        if payload is None:
            continue
        count += 1
        if args.dry_run:
            print(payload)
        else:
            subprocess.run(['mosquitto_pub', '-h', args.host, '-p', args.port,
                            '-u', 'artemis', '-P', 'artemis', '-t', 'moqui-log',
                            '-m', payload], check=True)
    return 0

if __name__ == '__main__':
    raise SystemExit(main())

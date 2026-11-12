#!/usr/bin/env python3
"""Build and run the portable IoT runtime against a host PAL (no ESP hardware)."""
from pathlib import Path
import argparse
import json
import os
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / 'components/moqui'
HOST = ROOT / 'tests/host'

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sanitize', action='store_true')
    args = parser.parse_args()
    dirs = sorted({p.parent for p in COMPONENT.rglob('*.h')})
    sources = sorted(p for p in COMPONENT.rglob('*.c') if 'platform' not in p.parts)
    with tempfile.TemporaryDirectory(prefix='moqui-iot-host-') as tmp:
        tmp = Path(tmp)
        # Match ESP-IDF's embedded text-file symbols, including the final NUL.
        embed = []
        for p in sorted((COMPONENT / 'runtime/component/mantle-hvac/data').glob('*.json')):
            symbol = '_binary_' + re.sub(r'[^a-zA-Z0-9]', '_', p.name)
            content = p.read_text()
            embed.append(f'const char {symbol}_start[] = {json.dumps(content)};')
            embed.append(f'__asm__(".global {symbol}_end\\n.set {symbol}_end, {symbol}_start + {len(content.encode()) + 1}");')
        (tmp / 'recipes.c').write_text('\n'.join(embed))
        flags = ['-std=c11', '-g', '-O1', '-Wall', '-Wextra', '-Werror=implicit-function-declaration', '-Werror=incompatible-pointer-types', '-pthread']
        if args.sanitize:
            flags += ['-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-fno-pie', '-no-pie']
        includes = ['-I'+str(HOST)] + ['-I'+str(p) for p in dirs]
        compiler = os.environ.get('CC', 'cc')
        # Compile both actual ESP entry-point variants using only host declarations.
        for variant in ([], ['-DCONFIG_MOQUI_ENABLE_TEST_SUITE=1']):
            subprocess.run([compiler, *flags, *includes, *variant, '-fsyntax-only', str(ROOT/'main/main.c')], check=True)
        subprocess.run([compiler, *flags, *includes, *map(str, sources),
                        str(HOST/'platform.c'), str(HOST/'test_runtime.c'), str(tmp/'recipes.c'),
                        '-lm', '-o', str(tmp/'test-runtime')], check=True)
        subprocess.run([compiler, *flags, *includes,
                        str(COMPONENT/'platform/esp32/mqtt_platform.c'),
                        str(HOST/'test_mqtt_platform.c'), '-o', str(tmp/'test-mqtt')], check=True)
        subprocess.run([str(tmp/'test-mqtt')], check=True)
        run = subprocess.run([str(tmp/'test-runtime')], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if run.returncode:
            print(run.stdout[-12000:]); print(run.stderr); raise SystemExit(run.returncode)
        print(run.stdout.splitlines()[-1])

if __name__ == '__main__':
    main()

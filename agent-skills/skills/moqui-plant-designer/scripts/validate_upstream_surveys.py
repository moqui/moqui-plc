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
import json
from pathlib import Path

from survey_validation import validate_upstream_surveys


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate upstream engineering surveys before seed/PLC generation")
    parser.add_argument("session_dir", type=Path, help="Saved session directory")
    parser.add_argument("--json", action="store_true", help="Print validation summary as JSON")
    args = parser.parse_args()

    summary = validate_upstream_surveys(args.session_dir.resolve())
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print("Upstream engineering surveys validated.")
        print(f"Subsystems: {len(summary['subsystemIds'])}")
        print(f"Devices: {len(summary['deviceIds'])}")
        print(f"Signals: {len(summary['signalIds'])}")
        print(f"Live parameters: {len(summary.get('liveParameterIds', []))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

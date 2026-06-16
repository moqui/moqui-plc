#!/usr/bin/env python3
"""Check the manually maintained AX Motion overrides without regenerating them.

The canonical IEC files remain the API reference. Axis.st and AxisGroup.st are
never emitted by the converter. This checker records their source hashes and
fails only when a requested AX override is missing. It deliberately does not
claim semantic equivalence; that requires compilation and TIA Portal tests.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_IEC_ROOT = REPO_ROOT / "iec61131" / "moqui"
DEFAULT_AX_ROOT = REPO_ROOT / "simatic-ax" / "src" / "moqui"
DEFAULT_STATE = REPO_ROOT / "simatic-ax" / "docs" / "motion-override-state.json"

MOTION_OVERRIDES = (
    Path("framework/src/main/org/moqui/motion/Axis.st"),
    Path("framework/src/main/org/moqui/motion/AxisGroup.st"),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Check stable AX Motion overrides.")
    parser.add_argument("--iec-root", default=str(DEFAULT_IEC_ROOT))
    parser.add_argument("--ax-root", default=str(DEFAULT_AX_ROOT))
    parser.add_argument("--state", default=str(DEFAULT_STATE))
    parser.add_argument("--allow-missing", action="store_true")
    args = parser.parse_args()

    iec_root = Path(args.iec_root).resolve()
    ax_root = Path(args.ax_root).resolve()
    state_path = Path(args.state).resolve()
    previous = {}
    if state_path.exists():
        previous = json.loads(state_path.read_text(encoding="utf-8"))

    state: dict[str, dict[str, object]] = {}
    missing: list[str] = []
    changed: list[str] = []

    for relative in MOTION_OVERRIDES:
        iec_path = iec_root / relative
        ax_path = ax_root / relative
        if not iec_path.exists():
            raise FileNotFoundError(f"Canonical Motion source missing: {iec_path}")

        iec_hash = sha256(iec_path)
        ax_exists = ax_path.exists()
        entry = {
            "canonical_iec_sha256": iec_hash,
            "ax_override_present": ax_exists,
            "ax_override_sha256": sha256(ax_path) if ax_exists else None,
        }
        old_entry = previous.get(relative.as_posix(), {})
        if old_entry.get("canonical_iec_sha256") not in (None, iec_hash):
            changed.append(relative.as_posix())
        if not ax_exists:
            missing.append(relative.as_posix())
        state[relative.as_posix()] = entry

    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    for item in changed:
        print(f"WARNING: canonical IEC Motion source changed: {item}")
    for item in missing:
        print(f"MISSING: manual AX Motion override: {item}")
    if missing and not args.allow_missing:
        return 2
    print("Motion override state written to", state_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

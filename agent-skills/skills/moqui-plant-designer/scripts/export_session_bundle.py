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
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main() -> int:
    parser = argparse.ArgumentParser(description="Export a saved Moqui plant-design session as a zip bundle")
    parser.add_argument("session_dir", type=Path, help="Path to the saved session directory")
    parser.add_argument("--output", type=Path, help="Optional zip output path")
    args = parser.parse_args()

    session_dir = args.session_dir.resolve()
    if not session_dir.is_dir():
        raise SystemExit(f"Session directory not found: {session_dir}")

    exports_dir = session_dir / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    zip_path = args.output.resolve() if args.output else exports_dir / f"{session_dir.name}.zip"
    manifest_path = zip_path.with_suffix(".manifest.json")

    file_entries: list[dict[str, str | int]] = []
    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as archive:
        for path in sorted(session_dir.rglob("*")):
            if not path.is_file():
                continue
            if path == zip_path or path == manifest_path:
                continue
            rel = path.relative_to(session_dir)
            archive.write(path, arcname=str(rel))
            file_entries.append(
                {
                    "path": str(rel),
                    "size": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )

    manifest = {
        "sessionId": session_dir.name,
        "exportedAt": utc_now(),
        "zipFile": str(zip_path.name),
        "files": file_entries,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote session bundle to {zip_path}")
    print(f"Wrote manifest to {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

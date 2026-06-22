#!/usr/bin/env python3
"""
Offline extraction of recipe data from the moqui DB — no gateway required.

Two modes:

  --mode definition   (default)
      Extracts ParameterDef metadata for a DeviceRuleSet and writes a CSV
      that update-recipe-definition-from-csv.py can feed directly to the
      CODESYS ScriptEngine to populate a RecipeDefinition object.

      Output columns:
          variableName  — CODESYS variable path (same derivation as the
                          gateway parameterName: DRI.REQUEST_ITEM_NAME,
                          then PARAMETER_ALIAS, then DEVICE_NAME.PARAMETER_NAME)
          name          — ParameterDef.parameterName  (display name)
          comment       — ParameterDef.description    (free text / unit)
          min_value     — ParameterDef.minValue
          max_value     — ParameterDef.maxValue
          parameter_code — ParameterDef.parameterCode (for sorting / reference)
          parameter_type — ParameterDef.parameterTypeEnumId

  --mode recipes
      Extracts actual parameter values and writes .txtrecipe files in the
      same format that CODESYS and export-ax-recipes.py already consume.
      Useful for offline development without running the full gateway.

      One .txtrecipe file is written per (ruleSetName, priority) group,
      named  <ruleSetName>_p<NN>.txtrecipe  (same naming as gateway export).

Usage examples
--------------
    python scripts/export-recipe-definition-from-db.py \\
        --rule-set-id VPL_RULESET_1 \\
        --db-url "postgresql://moqui:moqui@localhost:5432/moqui"

    python scripts/export-recipe-definition-from-db.py \\
        --rule-set-id VPL_RULESET_1 \\
        --mode recipes \\
        --output-dir iec61131/moqui/runtime/component/mantle-hvac/data \\
        --db-url "postgresql://moqui:moqui@localhost:5432/moqui"

    python scripts/export-recipe-definition-from-db.py \\
        --rule-set-id VPL_RULESET_1 \\
        --device-id  HVAC_PLC_01 \\
        --db-url "postgresql://moqui:moqui@localhost:5432/moqui"

Dependencies
------------
    pip install psycopg2-binary       # or psycopg2
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path
from typing import Any

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print(
        "ERROR: psycopg2 is required.  Install with:  pip install psycopg2-binary",
        file=sys.stderr,
    )
    sys.exit(1)


SCRIPT_DIR = Path(__file__).parent

DEFAULT_DB_URL = "postgresql://moqui:moqui@localhost:5432/moqui"
DEFAULT_OUTPUT_DIR_DEFINITION = str(SCRIPT_DIR)
DEFAULT_OUTPUT_DIR_RECIPES = "iec61131/moqui/runtime/component/mantle-hvac/data"

# ---------------------------------------------------------------------------
# SQL — definition mode
# Same parameterName derivation as device.config.export.sql.query in
# application.properties, but selects ParameterDef metadata instead of values.
# ---------------------------------------------------------------------------
DEFINITION_SQL = """
SELECT
    COALESCE(
        NULLIF(MAX(dri.REQUEST_ITEM_NAME), ''),
        NULLIF(p.PARAMETER_ALIAS, ''),
        COALESCE(phdev.DEVICE_NAME, dr.DEVICE_ID) || '.' || pd.PARAMETER_NAME
    ) AS variable_name,
    pd.PARAMETER_NAME       AS name,
    pd.DESCRIPTION          AS comment,
    pd.PARAMETER_CODE       AS parameter_code,
    pd.MIN_VALUE            AS min_value,
    pd.MAX_VALUE            AS max_value,
    pd.PARAMETER_TYPE_ENUM_ID AS parameter_type
FROM DEVICE_RULE_SET drs
INNER JOIN DEVICE_RULE dr
    ON dr.DEVICE_RULE_SET_ID = drs.DEVICE_RULE_SET_ID
INNER JOIN DEVICE_CONFIG dc
    ON dc.DEVICE_CONFIG_ID = dr.DEVICE_CONFIG_ID
LEFT  JOIN PHYSICAL_DEVICE phdev
    ON phdev.DEVICE_ID = dr.DEVICE_ID
INNER JOIN PARAMETER p
    ON p.DEVICE_CONFIG_ID = dc.DEVICE_CONFIG_ID
INNER JOIN PARAMETER_DEF pd
    ON pd.PARAMETER_DEF_ID = p.PARAMETER_DEF_ID
LEFT  JOIN DEVICE_REQUEST_ITEM dri
    ON dri.PARAMETER_ID = p.PARAMETER_ID
WHERE drs.DEVICE_RULE_SET_ID = %(rule_set_id)s
  AND (%(device_id)s IS NULL OR dr.DEVICE_ID = %(device_id)s)
GROUP BY
    pd.PARAMETER_DEF_ID, pd.PARAMETER_CODE, pd.PARAMETER_NAME,
    pd.DESCRIPTION, pd.MIN_VALUE, pd.MAX_VALUE, pd.PARAMETER_TYPE_ENUM_ID,
    p.PARAMETER_ID, p.PARAMETER_ALIAS,
    phdev.DEVICE_NAME, dr.DEVICE_ID
ORDER BY pd.PARAMETER_CODE, pd.PARAMETER_NAME
"""

# ---------------------------------------------------------------------------
# SQL — recipes mode
# Mirrors device.config.export.sql.query exactly (scalar parameters only;
# trajectory rows are omitted since txtrecipe does not carry them).
# ---------------------------------------------------------------------------
RECIPES_SQL = """
WITH base AS (
    SELECT
        drs.RULE_SET_NAME,
        dr.PRIORITY,
        dc.DEVICE_CONFIG_ID,
        COALESCE(phdev.DEVICE_NAME, dr.DEVICE_ID) AS device_name
    FROM DEVICE_RULE_SET drs
    INNER JOIN DEVICE_RULE dr
        ON dr.DEVICE_RULE_SET_ID = drs.DEVICE_RULE_SET_ID
    INNER JOIN DEVICE_CONFIG dc
        ON dc.DEVICE_CONFIG_ID = dr.DEVICE_CONFIG_ID
    LEFT JOIN PHYSICAL_DEVICE phdev
        ON phdev.DEVICE_ID = dr.DEVICE_ID
    WHERE drs.DEVICE_RULE_SET_ID = %(rule_set_id)s
      AND (%(device_id)s IS NULL OR dr.DEVICE_ID = %(device_id)s)
)
SELECT
    b.RULE_SET_NAME AS rule_set_name,
    b.PRIORITY      AS priority,
    COALESCE(
        NULLIF(MAX(dri.REQUEST_ITEM_NAME), ''),
        NULLIF(p.PARAMETER_ALIAS, ''),
        b.device_name || '.' || pd.PARAMETER_NAME
    ) AS parameter_name,
    CASE
        WHEN p.NUMERIC_VALUE     IS NOT NULL THEN CAST(p.NUMERIC_VALUE AS VARCHAR)
        WHEN p.PARAMETER_ENUM_ID IS NOT NULL THEN p.PARAMETER_ENUM_ID
        ELSE p.SYMBOLIC_VALUE
    END AS parameter_value
FROM base b
INNER JOIN PARAMETER p
    ON p.DEVICE_CONFIG_ID = b.DEVICE_CONFIG_ID
INNER JOIN PARAMETER_DEF pd
    ON pd.PARAMETER_DEF_ID = p.PARAMETER_DEF_ID
LEFT JOIN DEVICE_REQUEST_ITEM dri
    ON dri.PARAMETER_ID = p.PARAMETER_ID
GROUP BY
    b.RULE_SET_NAME, b.PRIORITY,
    p.PARAMETER_ID, p.PARAMETER_ALIAS,
    p.NUMERIC_VALUE, p.PARAMETER_ENUM_ID, p.SYMBOLIC_VALUE,
    b.device_name, pd.PARAMETER_NAME, pd.PARAMETER_CODE
ORDER BY b.PRIORITY, pd.PARAMETER_CODE, pd.PARAMETER_NAME
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Offline extraction of recipe data from the moqui DB."
    )
    parser.add_argument(
        "--rule-set-id",
        required=True,
        metavar="ID",
        help="DEVICE_RULE_SET_ID to export.",
    )
    parser.add_argument(
        "--device-id",
        default=None,
        metavar="ID",
        help="Optional DEVICE_ID filter (exports all devices in the rule set if omitted).",
    )
    parser.add_argument(
        "--mode",
        choices=["definition", "recipes"],
        default="definition",
        help=(
            "'definition' exports ParameterDef metadata as recipe-variables.csv "
            "(default); 'recipes' exports parameter values as .txtrecipe files."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        metavar="DIR",
        help=(
            "Output directory. Defaults to the scripts/ directory for 'definition' "
            "mode, or iec61131/.../data for 'recipes' mode."
        ),
    )
    parser.add_argument(
        "--db-url",
        default=os.environ.get("MOQUI_DB_URL", DEFAULT_DB_URL),
        metavar="URL",
        help=(
            "PostgreSQL connection URL (default: %(default)s). "
            "Can also be set via MOQUI_DB_URL environment variable."
        ),
    )
    return parser.parse_args()


def connect(db_url: str):
    return psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)


def run_definition(conn, rule_set_id: str, device_id: str | None, output_dir: Path) -> None:
    with conn.cursor() as cur:
        cur.execute(DEFINITION_SQL, {"rule_set_id": rule_set_id, "device_id": device_id})
        rows = cur.fetchall()

    if not rows:
        print(f"WARNING: no ParameterDef rows found for rule set '{rule_set_id}'.", file=sys.stderr)
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "recipe-variables.csv"

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "variableName", "name", "comment",
                "min_value", "max_value",
                "parameter_code", "parameter_type",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "variableName":   row["variable_name"] or "",
                    "name":           row["name"] or "",
                    "comment":        row["comment"] or "",
                    "min_value":      _fmt_decimal(row["min_value"]),
                    "max_value":      _fmt_decimal(row["max_value"]),
                    "parameter_code": row["parameter_code"] or "",
                    "parameter_type": row["parameter_type"] or "",
                }
            )

    print(f"Wrote {len(rows)} variable(s) to {out_path}")
    print(
        f"Next step: run update-recipe-definition-from-csv.py --csv {out_path} "
        f"inside the CODESYS Script Engine."
    )


def run_recipes(conn, rule_set_id: str, device_id: str | None, output_dir: Path) -> None:
    with conn.cursor() as cur:
        cur.execute(RECIPES_SQL, {"rule_set_id": rule_set_id, "device_id": device_id})
        rows = cur.fetchall()

    if not rows:
        print(f"WARNING: no parameter values found for rule set '{rule_set_id}'.", file=sys.stderr)
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    # Group by (rule_set_name, priority)
    from collections import defaultdict
    groups: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (row["rule_set_name"], int(row["priority"] or 0))
        groups[key].append(row)

    count = 0
    for (rule_set_name, priority), group_rows in sorted(groups.items()):
        filename = f"{rule_set_name}_p{priority:02d}.txtrecipe"
        out_path = output_dir / filename
        lines = [
            f"{r['parameter_name']}:={r['parameter_value']}"
            for r in group_rows
            if r["parameter_name"] and r["parameter_value"] is not None
        ]
        out_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        print(f"  wrote {filename}  ({len(lines)} parameters)")
        count += 1

    print(f"Done. Generated {count} .txtrecipe file(s) in {output_dir}")


def _fmt_decimal(value: Any) -> str:
    if value is None:
        return ""
    return str(value).rstrip("0").rstrip(".") if "." in str(value) else str(value)


def main() -> None:
    args = parse_args()

    output_dir = Path(args.output_dir) if args.output_dir else (
        SCRIPT_DIR if args.mode == "definition" else Path(DEFAULT_OUTPUT_DIR_RECIPES)
    )

    print(f"Connecting to {args.db_url} …")
    try:
        conn = connect(args.db_url)
    except Exception as e:
        print(f"ERROR: cannot connect to DB: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        if args.mode == "definition":
            run_definition(conn, args.rule_set_id, args.device_id, output_dir)
        else:
            run_recipes(conn, args.rule_set_id, args.device_id, output_dir)
    finally:
        conn.close()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Offline extraction of recipe data from the moqui DB — no gateway required.

Two modes:

  --mode definition   (default)
      Extracts ParameterDef metadata for a DeviceRuleSet and writes a CSV
      that update-recipe-definition-from-csv.py can feed directly to the
      CODESYS ScriptEngine to populate a RecipeDefinition object.

      Output columns:
          variableName  — CODESYS variable path, as moqui-device's export names
                          it: DRI.REQUEST_ITEM_NAME, else dev.<alias> (DtPLC),
                          dev.<deviceName>.<alias> (DtMoquiPlc*), else the alias
                          or <deviceName>.<parameterName>
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

      --layout tasks (default): one .txtrecipe file per recipe task, a
      DeviceRule of the rule set that is no part of another (parentRuleId
      empty), with all of its parts (the rules whose parentRuleId is it, at
      any depth), named  <configName>.<ruleSetName>.txtrecipe  after the
      task's DeviceConfig: the CODESYS <Recipe>.<Definition>.txtrecipe naming
      and moqui-device's export of a task (CivilCooling.HvacDeviceConfig.txtrecipe
      for the HVAC demo's rule set HvacCivilRules, ruleSetName HvacDeviceConfig).
      --task-id exports one task only.

      --layout priority: the former layout, one file per rule priority over
      every rule of the set, named  <ruleSetName>_p<NN>.txtrecipe  (moqui-device's
      export of a whole rule set).

  In definition mode a variable is written once, however many recipes set it.

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

    python scripts/export-recipe-definition-from-db.py \\
        --rule-set-id HvacCivilRules \\
        --mode recipes \\
        --task-id HvacCcProcessRule \\
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
# The CODESYS variable name of a parameter, as moqui-device names it (Devices.js recipeName, the export#DeviceConfig of the
# gateway): the name of a DeviceRequestItem of the parameter; else, by the DeviceConfig's device type, dev.<alias> for the
# PLC (DtPLC), dev.<deviceName>.<alias> for a Moqui PLC device (DtMoquiPlc*), and the alias or <deviceName>.<parameterName>
# for any other; the alias is Parameter.parameterAlias, else ParameterDef.parameterName.
# ---------------------------------------------------------------------------
def variable_name_sql(device_type: str, device_name: str) -> str:
    alias = "COALESCE(NULLIF(p.PARAMETER_ALIAS, ''), pd.PARAMETER_NAME)"
    return f"""COALESCE(
        NULLIF(MAX(dri.REQUEST_ITEM_NAME), ''),
        CASE
            WHEN {device_type} = 'DtPLC' THEN 'dev.' || {alias}
            WHEN {device_type} LIKE 'DtMoquiPlc%%' THEN 'dev.' || {device_name} || '.' || {alias}
            ELSE COALESCE(NULLIF(p.PARAMETER_ALIAS, ''), {device_name} || '.' || pd.PARAMETER_NAME)
        END
    )"""


# ---------------------------------------------------------------------------
# SQL — definition mode
# The variable names of variable_name_sql, with ParameterDef metadata instead of values.
# ---------------------------------------------------------------------------
DEFINITION_SQL = """
SELECT
    """ + variable_name_sql("dc.DEVICE_TYPE_ENUM_ID", "COALESCE(phdev.DEVICE_NAME, dr.DEVICE_ID)") + """ AS variable_name,
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
    phdev.DEVICE_NAME, dr.DEVICE_ID, dc.DEVICE_TYPE_ENUM_ID
ORDER BY pd.PARAMETER_CODE, pd.PARAMETER_NAME
"""

# ---------------------------------------------------------------------------
# SQL — recipes mode
# Scalar parameters only; trajectory rows are omitted since txtrecipe does not carry them.
# ---------------------------------------------------------------------------
# The recipe tasks of the rule set (no parentRuleId; with --task-id that one, with --device-id those of that device)
# and their parts at any depth, each part with its task: the tree moqui-device applies and exports as one recipe.
TASK_TREE_SQL = """
WITH RECURSIVE task_tree (TASK_ID, DEVICE_RULE_ID) AS (
    SELECT dr.DEVICE_RULE_ID, dr.DEVICE_RULE_ID
    FROM DEVICE_RULE dr
    WHERE dr.DEVICE_RULE_SET_ID = %(rule_set_id)s
      AND dr.PARENT_RULE_ID IS NULL
      AND (%(task_id)s IS NULL OR dr.DEVICE_RULE_ID = %(task_id)s)
      AND (%(device_id)s IS NULL OR dr.DEVICE_ID = %(device_id)s)
    UNION
    SELECT t.TASK_ID, part.DEVICE_RULE_ID
    FROM DEVICE_RULE part
    INNER JOIN task_tree t ON part.PARENT_RULE_ID = t.DEVICE_RULE_ID
    WHERE part.DEVICE_RULE_SET_ID = %(rule_set_id)s
)
"""

# The values of each recipe task: the tree's configurations, named as the gateway export names them, with the file name
# <the task's configName>.<ruleSetName>.
TASK_RECIPES_SQL = TASK_TREE_SQL + """
, base AS (
    SELECT
        t.TASK_ID,
        COALESCE(NULLIF(task_config.CONFIG_NAME, ''), task.RULE_NAME, t.TASK_ID) || '.' || drs.RULE_SET_NAME AS recipe_name,
        dc.DEVICE_CONFIG_ID,
        dc.DEVICE_TYPE_ENUM_ID AS device_type,
        COALESCE(phdev.DEVICE_NAME, dr.DEVICE_ID) AS device_name
    FROM task_tree t
    INNER JOIN DEVICE_RULE dr ON dr.DEVICE_RULE_ID = t.DEVICE_RULE_ID
    INNER JOIN DEVICE_RULE task ON task.DEVICE_RULE_ID = t.TASK_ID
    INNER JOIN DEVICE_RULE_SET drs ON drs.DEVICE_RULE_SET_ID = task.DEVICE_RULE_SET_ID
    LEFT JOIN DEVICE_CONFIG task_config ON task_config.DEVICE_CONFIG_ID = task.DEVICE_CONFIG_ID
    INNER JOIN DEVICE_CONFIG dc ON dc.DEVICE_CONFIG_ID = dr.DEVICE_CONFIG_ID
    LEFT JOIN PHYSICAL_DEVICE phdev ON phdev.DEVICE_ID = dr.DEVICE_ID
)
SELECT
    b.recipe_name AS recipe_name,
    """ + variable_name_sql("b.device_type", "b.device_name") + """ AS parameter_name,
    CASE
        WHEN p.NUMERIC_VALUE     IS NOT NULL THEN CAST(p.NUMERIC_VALUE AS VARCHAR)
        WHEN p.PARAMETER_ENUM_ID IS NOT NULL THEN p.PARAMETER_ENUM_ID
        ELSE p.SYMBOLIC_VALUE
    END AS parameter_value
FROM base b
INNER JOIN PARAMETER p ON p.DEVICE_CONFIG_ID = b.DEVICE_CONFIG_ID
INNER JOIN PARAMETER_DEF pd ON pd.PARAMETER_DEF_ID = p.PARAMETER_DEF_ID
LEFT JOIN DEVICE_REQUEST_ITEM dri ON dri.PARAMETER_ID = p.PARAMETER_ID
GROUP BY
    b.recipe_name, p.PARAMETER_ID, p.PARAMETER_ALIAS,
    p.NUMERIC_VALUE, p.PARAMETER_ENUM_ID, p.SYMBOLIC_VALUE,
    b.device_type, b.device_name, pd.PARAMETER_NAME, pd.PARAMETER_CODE
ORDER BY b.recipe_name, pd.PARAMETER_CODE, pd.PARAMETER_NAME
"""

# --layout priority: every rule of the set by priority, as before the recipe tasks
RECIPES_SQL = """
WITH base AS (
    SELECT
        drs.RULE_SET_NAME,
        dr.PRIORITY,
        dc.DEVICE_CONFIG_ID,
        dc.DEVICE_TYPE_ENUM_ID AS device_type,
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
    """ + variable_name_sql("b.device_type", "b.device_name") + """ AS parameter_name,
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
    b.device_type, b.device_name, pd.PARAMETER_NAME, pd.PARAMETER_CODE
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
        "--task-id",
        default=None,
        metavar="ID",
        help="recipes mode, tasks layout: export only this recipe task (a DEVICE_RULE_ID with no parent).",
    )
    parser.add_argument(
        "--layout",
        choices=["tasks", "priority"],
        default="tasks",
        help=(
            "recipes mode: 'tasks' writes one <configName>.<ruleSetName>.txtrecipe per recipe task with its parts "
            "(default); 'priority' writes one <ruleSetName>_p<NN>.txtrecipe per rule priority (the former layout)."
        ),
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

    # the recipes of a definition share its variables: each variable once, as its first row has it
    seen: set[str] = set()
    unique_rows = []
    for row in rows:
        name = row["variable_name"] or ""
        if name in seen:
            continue
        seen.add(name)
        unique_rows.append(row)
    rows = unique_rows

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


def run_task_recipes(conn, rule_set_id: str, task_id: str | None, device_id: str | None, output_dir: Path) -> None:
    """One <configName>.<ruleSetName>.txtrecipe per recipe task, with the values of the task and of its parts."""
    with conn.cursor() as cur:
        cur.execute(TASK_RECIPES_SQL, {"rule_set_id": rule_set_id, "task_id": task_id, "device_id": device_id})
        rows = cur.fetchall()

    if not rows:
        print(f"WARNING: no recipe task with parameter values found for rule set '{rule_set_id}'.", file=sys.stderr)
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    from collections import defaultdict
    recipes: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        recipes[row["recipe_name"]].append(row)

    count = 0
    for recipe_name, recipe_rows in sorted(recipes.items()):
        filename = f"{recipe_name}.txtrecipe"
        lines = []
        names: set[str] = set()
        for r in recipe_rows:
            # a variable set by two parts of one recipe is written once, as the first sets it
            if not r["parameter_name"] or r["parameter_value"] is None or r["parameter_name"] in names:
                continue
            names.add(r["parameter_name"])
            lines.append(f"{r['parameter_name']}:={r['parameter_value']}")
        (output_dir / filename).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        print(f"  wrote {filename}  ({len(lines)} parameters)")
        count += 1

    print(f"Done. Generated {count} .txtrecipe file(s) in {output_dir}")


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
        elif args.layout == "tasks":
            run_task_recipes(conn, args.rule_set_id, args.task_id, args.device_id, output_dir)
        else:
            run_recipes(conn, args.rule_set_id, args.device_id, output_dir)
    finally:
        conn.close()


if __name__ == "__main__":
    main()

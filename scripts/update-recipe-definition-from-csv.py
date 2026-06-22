# encoding:utf-8
"""
Update a CODESYS recipe definition from a CSV file.

Runs inside the CODESYS Script Engine (same execution context as export-codesys.py).
Reads a CSV that defines which PLC variables belong to a recipe definition, then
replaces the variable list of the target recipe definition object in the open project.

Usage (CODESYS Script Engine):
    Execute via Tools > Scripting > Execute Script File, or pass --csv and
    --definition on the command line when running via codesys.exe --script.

CSV format
----------
Required column:
    variableName   Full CODESYS variable path, e.g. MoquiStartInstance.dev.tempSetpoint

Optional columns (all become properties on ScriptRecipeVariable):
    name           Display name shown in the recipe editor
    comment        Free text, typically the engineering unit (e.g. "°C", "%RH")
    min_value      Minimum allowed value (string, as CODESYS stores it)
    max_value      Maximum allowed value

Rows with an empty variableName are silently skipped.

Example CSV
-----------
    variableName,name,comment,min_value,max_value
    MoquiStartInstance.dev.tempSetpoint,Temperature Setpoint,°C,10.0,50.0
    MoquiStartInstance.dev.rhSetpoint,Humidity Setpoint,%RH,0.0,100.0
    MoquiStartInstance.dev.airDistributionEnabled,Air Distribution,,0,1

Example command line
--------------------
    codesys.exe --profile "CODESYS V3.5 SP20" --script update-recipe-definition-from-csv.py -- \
        --csv path/to/recipe-variables.csv --definition "HvacRecipeDefinition"
"""

from __future__ import print_function

import argparse
import csv
import io
import os
import sys

try:
    text_type = unicode
except NameError:
    text_type = str


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()

DEFAULT_DEFINITION_NAME = "HvacRecipeDefinition"
DEFAULT_CSV = os.path.join(SCRIPT_DIR, "recipe-variables.csv")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Update a CODESYS recipe definition from a CSV file."
    )
    parser.add_argument(
        "--csv",
        default=DEFAULT_CSV,
        help="Path to the CSV file defining the recipe variables.",
    )
    parser.add_argument(
        "--definition",
        default=DEFAULT_DEFINITION_NAME,
        help='Name of the RecipeDefinition object in the CODESYS project (default: "{0}").'.format(
            DEFAULT_DEFINITION_NAME
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse the CSV and report what would change without modifying the project.",
    )
    return parser.parse_args(sys.argv[1:])


def read_csv(csv_path):
    """Return a list of dicts from the CSV. Each dict has at least 'variableName'."""
    rows = []
    with io.open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None or "variableName" not in reader.fieldnames:
            raise ValueError(
                "CSV must have a 'variableName' column. Found: {0}".format(reader.fieldnames)
            )
        for row in reader:
            var_name = (row.get("variableName") or "").strip()
            if not var_name:
                continue
            rows.append(
                {
                    "variableName": var_name,
                    "name":      (row.get("name")      or "").strip(),
                    "comment":   (row.get("comment")   or "").strip(),
                    "min_value": (row.get("min_value") or "").strip(),
                    "max_value": (row.get("max_value") or "").strip(),
                }
            )
    return rows


def find_recipe_manager(project):
    """Recursively search the project tree for the Recipe Manager object."""
    stack = list(project.get_children())
    while stack:
        obj = stack.pop()
        name = obj.get_name(False)
        if name in ("RecipeManager", "Recipe Manager"):
            return obj
        try:
            stack.extend(obj.get_children(False))
        except Exception:
            pass
    return None


def find_recipe_definition(recipe_mgr, definition_name):
    for obj in recipe_mgr.get_children(False):
        marker = getattr(obj, "is_recipedefinition", False)
        if marker and obj.get_name(False) == definition_name:
            return obj
    return None


def clear_variable_list(var_list):
    """Remove all variables from the recipe definition variable list."""
    while len(var_list) > 0:
        var_list.remove_at(0)


def populate_variable_list(var_list, rows):
    """Add variables from CSV rows to the variable list, setting optional properties."""
    for row in rows:
        var = var_list.add(row["variableName"])
        if row["name"]:
            var.name = row["name"]
        if row["comment"]:
            var.comment = row["comment"]
        if row["min_value"]:
            var.min_value = row["min_value"]
        if row["max_value"]:
            var.max_value = row["max_value"]
        print("  + {0}".format(row["variableName"]))


def report_dry_run(rows, definition_name):
    print("DRY RUN — no project changes will be made.")
    print("Target definition: {0}".format(definition_name))
    print("Variables to set ({0}):".format(len(rows)))
    for row in rows:
        extras = []
        if row["name"]:
            extras.append('name="{0}"'.format(row["name"]))
        if row["comment"]:
            extras.append('comment="{0}"'.format(row["comment"]))
        if row["min_value"] or row["max_value"]:
            extras.append("range=[{0}, {1}]".format(row["min_value"] or "?", row["max_value"] or "?"))
        suffix = "  ({0})".format(", ".join(extras)) if extras else ""
        print("  {0}{1}".format(row["variableName"], suffix))


def main():
    args = parse_args()

    csv_path = os.path.normpath(args.csv)
    if not os.path.exists(csv_path):
        print("ERROR: CSV file not found: {0}".format(csv_path))
        sys.exit(1)

    print("Reading CSV: {0}".format(csv_path))
    rows = read_csv(csv_path)
    print("  {0} variable(s) found.".format(len(rows)))

    if args.dry_run:
        report_dry_run(rows, args.definition)
        return

    # --- CODESYS project access (ScriptEngine context) ---
    try:
        project = projects.primary  # noqa: F821 (injected by CODESYS ScriptEngine)
    except NameError:
        print("ERROR: 'projects' is not available. This script must run inside the CODESYS Script Engine.")
        sys.exit(1)

    if project is None:
        print("ERROR: No project is currently open in CODESYS.")
        sys.exit(1)

    recipe_mgr = find_recipe_manager(project)
    if recipe_mgr is None:
        print("ERROR: 'Recipe Manager' object not found in the project.")
        sys.exit(1)

    recipe_def = find_recipe_definition(recipe_mgr, args.definition)
    if recipe_def is None:
        print(
            "ERROR: Recipe definition '{0}' not found under Recipe Manager.".format(args.definition)
        )
        existing = [
            obj.get_name(False)
            for obj in recipe_mgr.get_children(False)
            if getattr(obj, "is_recipedefinition", False)
        ]
        if existing:
            print("  Available definitions: {0}".format(", ".join(existing)))
        sys.exit(1)

    print("Updating definition: {0}".format(args.definition))
    var_list = recipe_def.variables

    print("  Clearing {0} existing variable(s)...".format(len(var_list)))
    clear_variable_list(var_list)

    print("  Adding {0} variable(s) from CSV...".format(len(rows)))
    populate_variable_list(var_list, rows)

    project.save()
    print("Done. Project saved.")

    try:
        system.ui.info(  # noqa: F821
            "Recipe definition '{0}' updated with {1} variable(s).".format(
                args.definition, len(rows)
            )
        )
    except Exception:
        pass


if __name__ == "__main__":
    main()

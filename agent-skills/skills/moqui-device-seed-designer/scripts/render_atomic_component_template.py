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

from render_seed_bundle import PLACEHOLDER_RE, TEMPLATE_MAP, render_template, strip_root


CATALOG_PATH = Path(__file__).resolve().parent.parent / "references" / "atomic-component-library.json"
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "references"


def load_catalog(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def humanize(raw: str) -> str:
    return raw.replace("_", " ").strip().title() or "Atomic Component"


def normalize(raw: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in raw.upper()).strip("_") or "DEVICE"


def parse_set_values(pairs: list[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for pair in pairs:
        if "=" not in pair:
            raise SystemExit(f"Invalid --set value {pair!r}; expected KEY=VALUE.")
        key, value = pair.split("=", 1)
        values[key] = value
    return values


def collect_placeholders(component_meta: dict, include_config: bool) -> list[str]:
    include_names = [component_meta["seedInclude"]]
    if include_config:
        include_names.extend(["device_config", component_meta["configInclude"]])
    placeholders: set[str] = set()
    for include_name in include_names:
        template_name = TEMPLATE_MAP[include_name]
        template_text = (TEMPLATES_DIR / template_name).read_text(encoding="utf-8")
        placeholders.update(PLACEHOLDER_RE.findall(template_text))
    return sorted(placeholders)


def derive_defaults(component_key: str, component_meta: dict, include_config: bool, overrides: dict[str, str] | None = None) -> dict[str, str]:
    overrides = overrides or {}
    device_id_variable = component_meta["deviceIdVariable"]
    device_name_variable = component_meta["nameVariable"]
    device_id = normalize(overrides.get(device_id_variable, f"{component_key}_template"))
    device_name = overrides.get(device_name_variable, humanize(device_id))
    values: dict[str, str] = {
        "PARENT_DEVICE_ID": "ROOT_DEVICE",
        device_id_variable: device_id,
        device_name_variable: device_name,
        component_meta["deviceTypeVariable"]: component_meta["deviceTypeEnumHint"],
        component_meta["purposeVariable"]: component_meta["purposeEnumHint"],
        component_meta["descriptionVariable"]: f"Canonical atomic-component template for {component_meta['logicalModel']}.",
        component_meta["parameterCodePrefixVariable"]: f"{normalize(component_key)}_{device_id}",
    }
    control_variable = component_meta.get("controlMethodVariable")
    if control_variable:
        values[control_variable] = component_meta["defaultControlMethodEnumId"]

    if include_config:
        values.update(
            {
                "DEVICE_ID": device_id,
                "DEVICE_TYPE_ENUM_ID": component_meta["deviceTypeEnumHint"],
                "CONTROL_METHOD_ENUM_ID": component_meta["defaultControlMethodEnumId"],
                "DEVICE_CONFIG_ID": f"CFG_{device_id}_TEMPLATE",
                "PARENT_DEVICE_CONFIG_ID": "",
                "CONFIG_NAME_TEMPLATE": f"{device_name} Prototype Config",
                "APPROXIMATED_FUNCTION_ID": "",
                "DEVICE_CONFIG_DESCRIPTION": f"Reusable prototype config for {component_meta['logicalModel']}.",
                "DEVICE_RULE_SET_ID": f"DRS_{device_id}_TEMPLATE",
                "PARENT_DEVICE_RULE_SET_ID": "",
                "RULE_SET_SEQUENCE_NUM": "1",
                "RULE_SET_NAME": f"{device_name} Prototype Rule Set",
                "RULE_SET_DESCRIPTION": f"Applies the prototype config for {device_name}.",
                "DEVICE_RULE_ID": f"DR_{device_id}_TEMPLATE",
                "PARENT_DEVICE_RULE_ID": "",
                "RULE_STATUS_ID": "",
                "RULE_STATUS_FLOW_ID": "",
                "RULE_NAME": f"Apply {device_name} Prototype Config",
                "RULE_DESCRIPTION": f"Bind the prototype config to {device_id}.",
                "RULE_SERVICE_NAME": "",
                "RULE_FLOATING_POINT_TOLERANCE": "0.000001",
                "RULE_TIME_TOLERANCE": "0",
            }
        )

    placeholders = collect_placeholders(component_meta, include_config)
    for placeholder in placeholders:
        if placeholder in values:
            continue
        if placeholder.startswith("PD_"):
            values[placeholder] = f"PD_{device_id}_{placeholder[3:]}"
        elif placeholder.startswith("CFG_P_"):
            values[placeholder] = f"CFG_P_{device_id}_{placeholder[6:]}"
        elif placeholder.startswith("P_"):
            values[placeholder] = f"P_{device_id}_{placeholder[2:]}"
        elif placeholder.endswith("_DEVICE_ID"):
            values[placeholder] = device_id
        elif placeholder.endswith("_NAME"):
            values[placeholder] = device_name
        elif placeholder.endswith("_DEVICE_TYPE_ENUM_ID"):
            values[placeholder] = component_meta["deviceTypeEnumHint"]
        elif placeholder.endswith("_PURPOSE_ENUM_ID"):
            values[placeholder] = component_meta["purposeEnumHint"]
        elif placeholder.endswith("_CONTROL_METHOD_ENUM_ID"):
            values[placeholder] = component_meta["defaultControlMethodEnumId"]
        elif placeholder.endswith("_DESCRIPTION"):
            values[placeholder] = f"Canonical atomic-component template for {component_meta['logicalModel']}."
        elif placeholder.endswith("_PARAMETER_CODE_PREFIX"):
            values[placeholder] = f"{normalize(component_key)}_{device_id}"
        elif placeholder.endswith("_ID_VALUE"):
            values[placeholder] = device_id
        elif placeholder.endswith("_NAME_VALUE"):
            values[placeholder] = device_name
        else:
            values[placeholder] = ""
    return values


def compose_seed(component_meta: dict, variables: dict[str, str], include_config: bool) -> str:
    include_names = [component_meta["seedInclude"]]
    if include_config:
        include_names.extend(["device_config", component_meta["configInclude"]])
    fragments: list[str] = []
    for include_name in include_names:
        template_name = TEMPLATE_MAP[include_name]
        template_text = (TEMPLATES_DIR / template_name).read_text(encoding="utf-8")
        fragments.append(render_template(strip_root(template_text), variables).rstrip())

    output = ['<?xml version="1.0" encoding="UTF-8"?>', '<entity-facade-xml type="seed">', ""]
    for index, fragment in enumerate(fragments):
        output.append(fragment)
        if index != len(fragments) - 1:
            output.append("")
    output.extend(["", "</entity-facade-xml>", ""])
    return "\n".join(output)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a canonical atomic-component seed/config template from the model-driven library")
    parser.add_argument("component", nargs="?", help="Atomic component key, for example actuator or process_pid")
    parser.add_argument("--catalog", type=Path, default=CATALOG_PATH, help="Atomic-component library catalog JSON")
    parser.add_argument("--list", action="store_true", help="List the available atomic components")
    parser.add_argument("--describe", action="store_true", help="Print the selected component metadata as JSON")
    parser.add_argument("--include-config", action="store_true", help="Compose the reusable DeviceConfig/DeviceRule prototype too")
    parser.add_argument("--variables", type=Path, help="Optional JSON file with variable overrides")
    parser.add_argument("--set", dest="sets", action="append", default=[], help="Inline override in the form KEY=VALUE")
    parser.add_argument("--output", type=Path, help="Output XML path for render mode")
    parser.add_argument("--spec-output", type=Path, help="Optional JSON bundle spec path to save alongside the rendered output")
    args = parser.parse_args()

    catalog = load_catalog(args.catalog)
    components = catalog["components"]

    if args.list:
        for component_key in sorted(components):
            component_meta = components[component_key]
            print(f"{component_key}: {component_meta['logicalModel']}")
        return 0

    if not args.component:
        raise SystemExit("Provide a component key or use --list.")
    if args.component not in components:
        raise SystemExit(f"Unknown component {args.component!r}. Known components: {', '.join(sorted(components))}")

    component_meta = components[args.component]
    if args.describe:
        print(json.dumps(component_meta, indent=2))
        return 0

    user_overrides: dict[str, str] = {}
    if args.variables:
        user_overrides.update(
            {str(key): str(value) for key, value in json.loads(args.variables.read_text(encoding="utf-8")).items()}
        )
    user_overrides.update(parse_set_values(args.sets))
    variables = derive_defaults(args.component, component_meta, args.include_config, overrides=user_overrides)
    variables.update(user_overrides)

    if args.spec_output:
        args.spec_output.parent.mkdir(parents=True, exist_ok=True)
        include_names = [component_meta["seedInclude"]]
        if args.include_config:
            include_names.extend(["device_config", component_meta["configInclude"]])
        args.spec_output.write_text(
            json.dumps({"includes": include_names, "variables": variables}, indent=2) + "\n",
            encoding="utf-8",
        )

    rendered = compose_seed(component_meta, variables, args.include_config)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

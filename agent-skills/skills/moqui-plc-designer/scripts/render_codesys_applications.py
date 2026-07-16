#!/usr/bin/env python3
"""Render one isolated CODESYS Application bundle per top-level controlled system."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from render_device_catalog_from_seed import to_lower_camel, to_upper_camel
from render_statusflow_templates import (
    load_template,
    parse_statusflow,
    render_main_status,
    render_output_assignments,
    render_predicate_assignments,
    render_predicate_declarations,
    st_assignment,
    write_rendered,
)

PLANT_SCRIPT_DIR = Path(__file__).resolve().parents[2] / "moqui-plant-designer" / "scripts"
if str(PLANT_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(PLANT_SCRIPT_DIR))

from survey_validation import load_upstream_survey_model, validate_fsm_surveys, validate_upstream_surveys


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
DEFAULT_TEMPLATES = SKILL_DIR / "references" / "plc-codegen-templates"
DEFAULT_FRAMEWORK = Path(__file__).resolve().parents[4] / "iec61131" / "moqui" / "framework"


def replace_text(path: Path, replacements: dict[str, str]) -> None:
    text = path.read_text(encoding="utf-8")
    for old, new in replacements.items():
        text = text.replace(old, new)
    unresolved = sorted({part.split("}", 1)[0] + "}" for part in text.split("${")[1:] if "}" in part})
    if unresolved:
        raise SystemExit(f"Unresolved template tokens in {path}: {', '.join(unresolved)}")
    path.write_text(text, encoding="utf-8")


def normalize_id(raw: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", raw).strip("_").upper()


def validate_orchestration_sources(component_root: Path, facade_path: Path, orchestration_paths: list[Path]) -> None:
    errors: list[str] = []
    facade_text = facade_path.read_text(encoding="utf-8")
    declared_fields = set(re.findall(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*", facade_text, re.MULTILINE))
    for path in orchestration_paths:
        text = path.read_text(encoding="utf-8")
        for marker in ("${", "__COND_", "__OUTPUT_", "__REQUEST_", "__APPLY_"):
            if marker in text:
                errors.append(f"{path.name} contains unresolved marker {marker}.")
        for field in re.findall(r"\bdev\.([A-Za-z_][A-Za-z0-9_]*)\s*:=", text):
            if field not in declared_fields:
                errors.append(f"{path.name} assigns undeclared DeviceFacade field dev.{field}.")
    if errors:
        raise SystemExit("Generated orchestration validation failed:\n- " + "\n- ".join(sorted(set(errors))))


def top_level_subsystem(owner_id: str, system_by_id: dict[str, dict]) -> str:
    current = owner_id
    seen: set[str] = set()
    while system_by_id[current]["parent_subsystem_id"]:
        if current in seen:
            raise SystemExit(f"Subsystem parent cycle detected at {current}.")
        seen.add(current)
        current = system_by_id[current]["parent_subsystem_id"]
    return current


def subsystem_status_names(fsm: dict) -> tuple[str, str, str, str]:
    base = to_upper_camel(fsm["component_name"] or fsm["fsm_id"])
    field = to_lower_camel(base) + "Status"
    return base + "Status", base + "Controller", field, to_lower_camel(base) + "LastStatus"


def render_subsystem_case_blocks(fsm: dict, items: list, upstream: dict) -> str:
    enum_by_id = {item.status_id: item.enum_name for item in items}
    transitions_by_from: dict[str, list[dict]] = {}
    for transition in sorted(fsm["transitions"], key=lambda row: (row["from_status_id"], row["precedence"])):
        transitions_by_from.setdefault(transition["from_status_id"], []).append(transition)
    status_type, _, status_field, _ = subsystem_status_names(fsm)
    blocks: list[str] = []
    state_by_id = {state["status_id"]: state for state in fsm["states"]}
    for item in items:
        lines = [f"    {status_type}.{item.enum_name}:"]
        lines.append(f"        logger(message := '{item.enum_name}.', level := LogLevel.DEBUG);")
        lines.append(f"        {render_output_assignments(state_by_id[item.status_id], upstream)}")
        transitions = transitions_by_from.get(item.status_id, [])
        for index, transition in enumerate(transitions):
            keyword = "IF" if index == 0 else "ELSIF"
            lines.append(f"        {keyword} {transition['condition']} THEN")
            target_fsm_id = transition["to_fsm_id"] or fsm["fsm_id"]
            if target_fsm_id == fsm["fsm_id"]:
                lines.append(f"            dev.{status_field} := {status_type}.{enum_by_id[transition['to_status_id']]};")
            else:
                if not transition["apply_assignments"]:
                    raise SystemExit(
                        f"Cross-flow transition in {fsm['fsm_id']} requires reviewed apply_assignments."
                    )
                lines.extend(f"            {st_assignment(row)}" for row in transition["apply_assignments"])
        if transitions:
            lines.append("        END_IF;")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def run_script(script: str, args: list[str], cwd: Path) -> None:
    result = subprocess.run([sys.executable, str(SCRIPT_DIR / script), *args], cwd=cwd, text=True, capture_output=True)
    if result.returncode:
        raise SystemExit(f"{script} failed:\n{result.stdout}\n{result.stderr}")


def render_application(
    session_dir: Path,
    seed_path: Path,
    output_root: Path,
    top_subsystem_id: str,
    fsms: list[dict],
    upstream: dict,
    templates_dir: Path,
    framework_source: Path,
    copy_framework: bool,
    namespace: str,
) -> dict:
    main_candidates = [fsm for fsm in fsms if fsm["owner_subsystem_id"] == top_subsystem_id]
    if len(main_candidates) != 1:
        raise SystemExit(
            f"Top-level system {top_subsystem_id} must own exactly one supervisor FSM; found {len(main_candidates)}."
        )
    main_fsm = main_candidates[0]
    explicit_application_ids = {fsm["application_id"] for fsm in fsms if fsm["application_id"]}
    if len(explicit_application_ids) > 1:
        raise SystemExit(
            f"Top-level system {top_subsystem_id} maps to conflicting application_id values: "
            + ", ".join(sorted(explicit_application_ids))
        )
    subsystem_fsms = sorted(
        (fsm for fsm in fsms if fsm is not main_fsm), key=lambda row: (row["call_sequence"], row["fsm_id"])
    )
    sequences = [fsm["call_sequence"] for fsm in subsystem_fsms]
    if len(sequences) != len(set(sequences)):
        raise SystemExit(f"Application {top_subsystem_id} has duplicate subsystem call_sequence values.")

    application_id = main_fsm["application_id"] or to_upper_camel(top_subsystem_id) + "Application"
    component_name = to_lower_camel(main_fsm["component_name"] or top_subsystem_id)
    application_root = output_root / application_id
    component_output_root = application_root / "runtime" / "component"
    component_root = component_output_root / component_name
    application_root.mkdir(parents=True, exist_ok=True)

    run_script(
        "render_statusflow_templates.py",
        [
            str(seed_path), main_fsm["status_flow_id"], "--session-dir", str(session_dir),
            "--component-name", component_name, "--namespace", namespace,
            "--output-root-override", str(component_output_root),
        ],
        SCRIPT_DIR.parents[3],
    )
    run_script(
        "render_device_catalog_from_seed.py",
        [
            str(seed_path), "--device-id", f"DG_{normalize_id(top_subsystem_id)}",
            "--component-name", component_name, "--namespace", namespace,
            "--session-dir", str(session_dir), "--output-root-override", str(component_output_root),
            "--allow-logical-root",
        ],
        SCRIPT_DIR.parents[3],
    )

    run_script(
        "render_live_parameter_mapper.py",
        [
            str(seed_path), "--device-id", f"DG_{normalize_id(top_subsystem_id)}",
            "--session-dir", str(session_dir),
            "--output", str(component_root / "src" / "main" / "org" / "moqui" / "util" / "json" / "JsonToParametersMapper.st"),
        ],
        SCRIPT_DIR.parents[3],
    )

    component_dir = component_root / "src" / "main" / namespace / component_name
    facade_path = component_root / "src" / "main" / "org" / "moqui" / "device" / "DeviceFacade.dut"
    main_path = component_dir / "Main.pou"
    all_predicates = [predicate for fsm in fsms for predicate in fsm["predicates"]]
    predicate_names = [row["name"] for row in all_predicates]
    if len(predicate_names) != len(set(predicate_names)):
        raise SystemExit(f"Application {application_id} reuses predicate names across FSMs; names must be Application-global.")

    subsystem_declarations: list[str] = []
    controller_declarations: list[str] = []
    init_calls: list[str] = []
    run_calls: list[str] = []
    trace_rows: list[dict] = []
    for fsm in subsystem_fsms:
        items, _ = parse_statusflow(seed_path, fsm["status_flow_id"])
        initial = next(item.enum_name for item in items if item.is_initial)
        status_type, controller_type, status_field, last_status_field = subsystem_status_names(fsm)
        controller_var = to_lower_camel(controller_type)
        subsystem_declarations.extend(
            [
                f"    {status_field} : {status_type} := {status_type}.{initial};",
                f"    {last_status_field} : {status_type} := {status_type}.{initial};",
            ]
        )
        controller_declarations.append(f"    {controller_var} : {controller_type}; (* sequence {fsm['call_sequence']} *)")
        init_calls.append(f"    {controller_var}(operationType := OperatingMode.Init, enable := FALSE);")
        run_calls.append(
            f"{controller_var}(operationType := operationType, enable := {fsm['enable_condition']}); "
            f"(* sequence {fsm['call_sequence']}: {fsm['fsm_id']} *)"
        )
        write_rendered(
            load_template(templates_dir / "SubsystemStatus.template.dut"),
            {"${SUBSYSTEM_STATUS_TYPE}": status_type, "${SUBSYSTEM_STATUS_ITEMS}": render_main_status(items)},
            component_dir / f"{status_type}.dut",
        )
        write_rendered(
            load_template(templates_dir / "SubsystemController.template.pou"),
            {
                "${SUBSYSTEM_CONTROLLER_TYPE}": controller_type,
                "${SUBSYSTEM_COMPONENT_NAME}": fsm["component_name"],
                "${SUBSYSTEM_STATUS_FIELD}": status_field,
                "${SUBSYSTEM_LAST_STATUS_FIELD}": last_status_field,
                "${SUBSYSTEM_STATUS_TYPE}": status_type,
                "${SUBSYSTEM_INITIAL_STATUS}": initial,
                "${SUBSYSTEM_PREDICATE_ASSIGNMENTS}": render_predicate_assignments(fsm),
                "${SUBSYSTEM_CASE_BLOCKS}": render_subsystem_case_blocks(fsm, items, upstream),
            },
            component_dir / f"{controller_type}.pou",
        )
        trace_rows.append(
            {
                "fsmId": fsm["fsm_id"], "statusFlowId": fsm["status_flow_id"],
                "ownerSubsystemId": fsm["owner_subsystem_id"], "callSequence": fsm["call_sequence"],
                "controller": f"src/main/{namespace}/{component_name}/{controller_type}.pou",
            }
        )

    predicate_declarations = render_predicate_declarations({"predicates": all_predicates})
    replace_text(
        facade_path,
        {
            "    (* Project predicates are generated from reviewed FSM surveys. *)": predicate_declarations,
            "    (* Subsystem FSM state fields are generated by render_codesys_applications.py. *)":
                "\n".join(subsystem_declarations) if subsystem_declarations else "    (* No subsystem FSMs. *)",
        },
    )
    replace_text(
        main_path,
        {
            "    (* No subsystem controllers generated by this single-FSM command. *)":
                "\n".join(controller_declarations) if controller_declarations else "    (* No subsystem controllers. *)",
            "    (* No subsystem controller initialization. *)":
                "\n".join(init_calls) if init_calls else "    (* No subsystem controller initialization. *)",
            "(* No subsystem controller calls. *)":
                "\n".join(run_calls) if run_calls else "(* No subsystem controller calls. *)",
        },
    )
    shutil.copy2(seed_path, component_root / "data" / "SurveyDerivedSeed.xml")
    if copy_framework:
        if not framework_source.is_dir():
            raise SystemExit(f"Framework source not found: {framework_source}")
        shutil.copytree(framework_source, application_root / "framework", dirs_exist_ok=True)

    trace_rows.insert(
        0,
        {
            "fsmId": main_fsm["fsm_id"], "statusFlowId": main_fsm["status_flow_id"],
            "ownerSubsystemId": main_fsm["owner_subsystem_id"], "callSequence": 0,
            "controller": f"src/main/{namespace}/{component_name}/Main.pou",
        },
    )
    orchestration_paths = [main_path, component_dir / "MainRuleEngine.pou"] + [
        component_dir / f"{subsystem_status_names(fsm)[1]}.pou" for fsm in subsystem_fsms
    ]
    validate_orchestration_sources(component_root, facade_path, orchestration_paths)
    trace_lines = [
        f"# {application_id} — PLC traceability",
        "",
        "| Sequence | FSM | Owner subsystem | StatusFlow | Controller |",
        "| ---: | --- | --- | --- | --- |",
    ]
    trace_lines.extend(
        f"| {row['callSequence']} | {row['fsmId']} | {row['ownerSubsystemId']} | {row['statusFlowId']} | `{row['controller']}` |"
        for row in trace_rows
    )
    trace_lines.extend(["", "All output functions and transition conditions were generated only after survey approval.", ""])
    (application_root / "plc-traceability.md").write_text("\n".join(trace_lines), encoding="utf-8")
    manifest = {
        "applicationId": application_id,
        "topLevelSubsystemId": top_subsystem_id,
        "componentName": component_name,
        "frameworkPath": "framework" if copy_framework else str(framework_source),
        "runtimeComponentPath": f"runtime/component/{component_name}",
        "fsmInvocationOrder": trace_rows,
        "developerActions": [
            "Create the CODESYS Application object with this unique applicationId.",
            "Import the dedicated framework and runtime component sources into this Application only.",
            "Create and configure control and communication tasks for this Application.",
            "Create the Application device tree manually and verify every connected device.",
            "When several Applications share one PLC device, select the Application responsible for device I/O in PLC Settings.",
        ],
    }
    (application_root / "application-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Render isolated CODESYS Application bundles from reviewed FSM surveys")
    parser.add_argument("--session-dir", type=Path, required=True)
    parser.add_argument("--seed", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--namespace", default="mantle")
    parser.add_argument("--templates-dir", type=Path, default=DEFAULT_TEMPLATES)
    parser.add_argument("--framework-source", type=Path, default=DEFAULT_FRAMEWORK)
    parser.add_argument("--no-copy-framework", action="store_true")
    args = parser.parse_args()
    session_dir = args.session_dir.resolve()
    validate_upstream_surveys(session_dir)
    upstream = load_upstream_survey_model(session_dir)
    fsm_model = validate_fsm_surveys(session_dir, upstream)
    if not fsm_model["fsms"]:
        raise SystemExit("No FSMs found in the session surveys.")
    not_approved = [fsm["fsm_id"] for fsm in fsm_model["fsms"] if not fsm["code_generation_approved"]]
    if not_approved:
        raise SystemExit("PLC code generation requires approval for FSMs: " + ", ".join(not_approved))
    unreviewed = [
        f"{fsm['fsm_id']}/{state['status_id']}"
        for fsm in fsm_model["fsms"] for state in fsm["states"] if not state["outputs_reviewed"]
    ]
    if unreviewed:
        raise SystemExit("PLC output functions require review: " + ", ".join(unreviewed))

    seed_path = (args.seed or session_dir / "seed-data" / "survey-derived-seed.xml").resolve()
    if not seed_path.is_file():
        raise SystemExit(f"Seed XML not found: {seed_path}")
    output_root = (args.output_root or session_dir / "generated-plc" / "codesys-applications").resolve()
    system_by_id = {row["subsystem_id"]: row for row in upstream["system_tree"]}
    grouped: dict[str, list[dict]] = {}
    for fsm in fsm_model["fsms"]:
        root_id = top_level_subsystem(fsm["owner_subsystem_id"], system_by_id)
        grouped.setdefault(root_id, []).append(fsm)
    manifests = [
        render_application(
            session_dir, seed_path, output_root, root_id, fsms, upstream,
            args.templates_dir, args.framework_source.resolve(), not args.no_copy_framework, args.namespace,
        )
        for root_id, fsms in sorted(grouped.items())
    ]
    application_ids = [manifest["applicationId"] for manifest in manifests]
    if len(application_ids) != len(set(application_ids)):
        raise SystemExit("CODESYS application_id values must be unique across top-level systems.")
    (output_root / "codesys-project-manifest.json").write_text(
        json.dumps({"applications": manifests}, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Rendered {len(manifests)} isolated CODESYS Application bundle(s) into {output_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

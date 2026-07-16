#!/usr/bin/env python3
"""Render a reviewable engineering dossier and, optionally, Wiki association seed data."""

from __future__ import annotations

import argparse
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from survey_validation import load_upstream_survey_model, validate_fsm_surveys, validate_upstream_surveys


MILESTONES = (
    "Raccolta distinte elettriche, schemi e datasheet",
    "Verifica dei cablaggi e della naming convention",
    "Configurazione del device tree",
    "Configurazione di drive, servo e reti vendor-specific",
    "Validazione delle condizioni di processo e dei predicati booleani",
    "Prove FAT/SAT",
    "Verifica temporale, logging e diagnostica",
    "Verifica dell'interfaccia verso il safety esterno",
)


def slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").upper() or "PLC_PROJECT"


def table(headers: list[str], rows: list[list[object]]) -> str:
    if not rows:
        return "_Nessun dato approvato._"
    head = "| " + " | ".join(headers) + " |"
    rule = "| " + " | ".join("---" for _ in headers) + " |"
    body = ["| " + " | ".join(str(cell).replace("|", "\\|") for cell in row) + " |" for row in rows]
    return "\n".join([head, rule, *body])


def render_markdown(model: dict, fsm_model: dict) -> str:
    scope = model["project_scope"]
    sections = [
        f"# Specifica ingegneristica — {scope['machine_name'] or 'progetto PLC'}",
        "",
        "> Documento derivato dalle survey e soggetto ad approvazione del developer PLC. "
        "Non costituisce validazione safety, certificazione o assunzione di responsabilità.",
        "",
        "## Ambito",
        "",
        f"- Processo: {scope['process_description'] or 'da definire'}",
        f"- Obiettivo di controllo: {scope['control_objective'] or 'da definire'}",
        f"- Confine safety: {scope['safety_scope'] or 'esterno al framework; da confermare'}",
        "",
        "## Piano HiveMind suggerito",
        "",
        *[f"- [ ] {item}" for item in MILESTONES],
        "",
        "## Sistemi e sottosistemi",
        "",
        table(
            ["ID", "Parent", "Nome", "Tipo", "Responsabilità"],
            [[r['subsystem_id'], r['parent_subsystem_id'], r['subsystem_name'], r['subsystem_type'], r['control_responsibility']] for r in model['system_tree']],
        ),
        "",
        "## Dispositivi foglia",
        "",
        table(
            ["ID", "Sottosistema", "Modello", "Classe Req/Ack", "Nome"],
            [[r['device_id'], r['parent_subsystem_id'], r['logical_model'], r['actuation_feedback_class'], r['physical_device_name']] for r in model['devices']],
        ),
        "",
        "## FSM di orchestrazione",
        "",
        table(
            ["FSM", "Owner", "StatusFlow", "Composizione", "Stati", "Transizioni"],
            [[f['fsm_id'], f['owner_subsystem_id'], f['status_flow_id'], f['composition'], len(f['states']), len(f['transitions'])] for f in fsm_model['fsms']],
        ),
        "",
        "I dati Moqui sono autoritativi per struttura, stati e archi. Predicati, output function, "
        "interlock e ordine di invocazione restano autoritativi nel codice PLC.",
        "",
        "## Parametri aggiornabili live approvati",
        "",
        table(
            ["Parametro esistente", "Chiave MQTT"],
            [[r['parameter_id'], r['mqtt_key']] for r in model['live_parameters'] if any(r.values())],
        ),
        "",
        "## Confine di comunicazione",
        "",
        "Moqui registra l'esito del gateway tramite callback REST. La responsabilità del tool termina "
        "alla pubblicazione MQTT v5 persistente o alla scrittura/polling OPC UA; non viene introdotto "
        "un protocollo applicativo parallelo di acknowledgement del PLC.",
        "",
    ]
    return "\n".join(sections)


def render_hivemind_project_seed(model: dict, work_effort_id: str) -> str:
    """Create a fresh HiveMind project tree using the canonical WorkEffort/Wiki pattern."""
    project_slug = slug(work_effort_id)
    wiki_space_id = f"WIKI_{project_slug}"
    wiki_page_id = f"WIKI_{project_slug}_SPEC"
    page_path = f"component://moqui-plc/WikiSpace/{project_slug}.md"
    project_name = model["project_scope"]["machine_name"] or work_effort_id
    root = ET.Element("entity-facade-xml", {"type": "seed"})
    ET.SubElement(root, "moqui.resource.wiki.WikiSpace", {
        "wikiSpaceId": wiki_space_id,
        "description": "Moqui PLC engineering dossier",
        "restrictView": "N",
        "rootPageLocation": page_path,
        "decoratorScreenLocation": "",
    })
    ET.SubElement(root, "moqui.resource.wiki.WikiPage", {
        "wikiPageId": wiki_page_id,
        "wikiSpaceId": wiki_space_id,
        "pagePath": "Engineering specification",
    })
    ET.SubElement(root, "mantle.work.effort.WorkEffort", {
        "workEffortId": work_effort_id,
        "workEffortName": f"PLC engineering - {project_name}",
        "workEffortTypeEnumId": "WetProject",
        "statusId": "WeInPlanning",
        "description": "Developer-owned machine automation project generated from approved engineering surveys.",
    })
    ET.SubElement(root, "mantle.work.effort.WikiPageWorkEffort", {
        "wikiPageId": wiki_page_id,
        "workEffortId": work_effort_id,
    })
    for index, milestone_name in enumerate(MILESTONES, start=1):
        milestone_id = f"{project_slug}_MS_{index:02d}"
        task_id = f"{project_slug}_T_{index:02d}"
        ET.SubElement(root, "mantle.work.effort.WorkEffort", {
            "workEffortId": milestone_id,
            "workEffortName": milestone_name,
            "rootWorkEffortId": work_effort_id,
            "workEffortTypeEnumId": "WetMilestone",
            "statusId": "WeInPlanning",
        })
        ET.SubElement(root, "mantle.work.effort.WorkEffort", {
            "workEffortId": task_id,
            "workEffortName": f"Eseguire e documentare: {milestone_name}",
            "rootWorkEffortId": work_effort_id,
            "workEffortTypeEnumId": "WetTask",
            "purposeEnumId": "WepTask",
            "statusId": "WeInPlanning",
            "description": "Attivita da completare, verificare e chiudere dal developer PLC; il tool non certifica il risultato.",
        })
        ET.SubElement(root, "mantle.work.effort.WorkEffortAssoc", {
            "workEffortId": milestone_id,
            "toWorkEffortId": task_id,
            "workEffortAssocTypeEnumId": "WeatMilestone",
            "fromDate": "2026-01-01 00:00:00",
            "sequenceNum": "1",
        })
    ET.indent(root, space="    ")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode")


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the approved engineering dossier from a saved session")
    parser.add_argument("--session-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--work-effort-id", help="Also emit WikiSpace/WikiPage association seed for this HiveMind project")
    parser.add_argument("--wiki-seed-output", type=Path)
    args = parser.parse_args()
    session_dir = args.session_dir.resolve()
    validate_upstream_surveys(session_dir)
    model = load_upstream_survey_model(session_dir)
    fsm_model = validate_fsm_surveys(session_dir, model)
    output = args.output or session_dir / "notes" / "engineering-specification.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_markdown(model, fsm_model), encoding="utf-8")
    print(f"Wrote engineering dossier to {output}")
    if args.work_effort_id:
        if not model["approvals"].get("hivemind_project_approved"):
            raise SystemExit("HiveMind project generation requires hivemind_project_approved: true.")
        project_slug = slug(args.work_effort_id)
        wiki_output = args.wiki_seed_output or session_dir / "seed-data" / "engineering-wiki-seed.xml"
        wiki_output.parent.mkdir(parents=True, exist_ok=True)
        wiki_output.write_text(
            render_hivemind_project_seed(model, args.work_effort_id),
            encoding="utf-8",
        )
        print(f"Wrote optional Wiki association seed to {wiki_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

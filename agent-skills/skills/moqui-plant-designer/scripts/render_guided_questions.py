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
from datetime import datetime, timezone
from pathlib import Path

from survey_validation import load_upstream_survey_model


ATOMIC_COMPONENT_LIBRARY_PATH = (
    Path(__file__).resolve().parents[2]
    / "moqui-device-seed-designer"
    / "references"
    / "atomic-component-library.json"
)

ACTUATION_FEEDBACK_EXPECTATIONS = {
    "DA-DF": {"actuation": 2, "feedback": 2},
    "SA-DF": {"actuation": 1, "feedback": 2},
    "SA-SAFD": {"actuation": 1, "feedback": 1},
    "SA-SDFD": {"actuation": 1, "feedback": 1},
    "SA-NO": {"actuation": 1, "feedback": 0},
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_session(session_dir: Path) -> tuple[Path, dict]:
    session_path = session_dir / "session.json"
    if not session_path.is_file():
        raise SystemExit(f"session.json not found in session directory: {session_dir}")
    return session_path, json.loads(session_path.read_text(encoding="utf-8"))


def load_atomic_library() -> dict:
    return json.loads(ATOMIC_COMPONENT_LIBRARY_PATH.read_text(encoding="utf-8"))


def build_guided_questions(model: dict, atomic_library: dict) -> dict:
    questions: list[dict[str, str]] = []
    stage = "system_decomposition"

    project_scope = model["project_scope"]
    if not project_scope["machine_name"] or not project_scope["control_objective"]:
        questions.append(
            {
                "stage": "system_decomposition",
                "question": "Qual e il nome macchina/impianto e qual e l'obiettivo di controllo principale?",
                "why": "Serve per fissare il root PLC, lo scope del sistema e la descrizione canonica del seed.",
            }
        )
    if not model["system_tree"] or not model["system_tree"][0]["subsystem_id"]:
        questions.append(
            {
                "stage": "system_decomposition",
                "question": "Qual e il primo sottosistema controllabile e come si scompone fino ai dispositivi elementari?",
                "why": "La decomposizione del sistema viene prima di ogni domanda su segnali, trasporti o FSM.",
            }
        )
        return {"stage": stage, "questions": questions}

    subsystem_ids = {row["subsystem_id"] for row in model["system_tree"] if row["subsystem_id"]}
    stage = "device_classification"
    devices = model["devices"]
    if not devices or not devices[0]["device_id"]:
        questions.append(
            {
                "stage": "device_classification",
                "question": "Quali sono i dispositivi elementari di ciascun sottosistema e con quale logical model vanno classificati?",
                "why": "Da questa scelta derivano automaticamente i parametri logici dell'atomic component.",
            }
        )
        return {"stage": stage, "questions": questions}

    for device in devices:
        device_id = device["device_id"]
        if not device_id:
            continue
        if not device["parent_subsystem_id"] or device["parent_subsystem_id"] not in subsystem_ids:
            questions.append(
                {
                    "stage": "device_classification",
                    "question": f"A quale sottosistema appartiene il device {device_id}?",
                    "why": "La membership del sottosistema guida DeviceGroup, FSM e scope dei gateway.",
                }
            )
        if not device["logical_model"]:
            questions.append(
                {
                    "stage": "device_classification",
                    "question": f"Il device {device_id} e un Actuator, ActuatorGroup, Axis, AxisGroup, ProcessPid o SignalMgmt?",
                    "why": "Il logical model determina il template canonico dei parametri logici.",
                }
            )
            continue
        if not device["actuation_feedback_class"]:
            questions.append(
                {
                    "stage": "device_classification",
                    "question": f"Qual e la classificazione DA-DF / SA-DF / SA-SAFD / SA-SDFD / SA-NO per {device_id}?",
                    "why": "La classe determina i segnali fisici attesi e il control method contestuale.",
                }
            )
            continue

        component_key = device["logical_model"]
        library_component = next(
            (meta for meta in atomic_library["components"].values() if meta["logicalModel"] == component_key),
            None,
        )
        if library_component:
            expectations = ACTUATION_FEEDBACK_EXPECTATIONS.get(device["actuation_feedback_class"], {"actuation": 0, "feedback": 0})
            actual_actuation = len(device["expected_actuation_signals"])
            actual_feedback = len(device["expected_feedback_signals"])
            if actual_actuation < expectations["actuation"] or actual_feedback < expectations["feedback"]:
                questions.append(
                    {
                        "stage": "signal_catalog",
                        "question": (
                            f"Per {device_id} ({device['logical_model']}) indica il cablaggio contestuale dei segnali: "
                            f"attesi almeno {expectations['actuation']} attuazioni e {expectations['feedback']} feedback, "
                            f"ma dichiarati {actual_actuation}/{actual_feedback}."
                        ),
                        "why": (
                            "I parametri logici dell'atomic component sono gia fissati dal modello; "
                            "qui mancano solo i segnali fisici contestuali."
                        ),
                    }
                )

    if questions:
        return {"stage": "signal_catalog", "questions": questions}

    stage = "signal_catalog"
    signal_ids_by_device: dict[str, list[dict]] = {}
    for signal in model["signals"]:
        if not signal["signal_id"]:
            continue
        signal_ids_by_device.setdefault(signal["device_id"], []).append(signal)

    if not model["signals"] or not model["signals"][0]["signal_id"]:
        questions.append(
            {
                "stage": "signal_catalog",
                "question": "Elenca tutti i segnali fisici normalizzati con naming rule, direzione, tipo IEC e polarita.",
                "why": "Il catalogo segnali e la sorgente di verita per IOFacade, DeviceRequest e validazioni successive.",
            }
        )
        return {"stage": stage, "questions": questions}

    for device in devices:
        if device["device_id"] and device["device_id"] not in signal_ids_by_device:
            questions.append(
                {
                    "stage": "signal_catalog",
                    "question": f"Quali segnali fisici appartengono al device {device['device_id']}?",
                    "why": "Ogni atomic component istanziato nel modello deve proiettarsi sui segnali fisici del contesto.",
                }
            )

    if questions:
        return {"stage": stage, "questions": questions}

    stage = "sampling_design"
    if not model["domains"] or not model["domains"][0]["domain_id"]:
        questions.append(
            {
                "stage": "sampling_design",
                "question": "Come raggruppi device e segnali per frequenza naturale e scan time?",
                "why": "I domini di campionamento guidano le partizioni automatiche delle DeviceRequest.",
            }
        )
        return {"stage": stage, "questions": questions}

    for domain in model["domains"]:
        if not domain["transport_projection"]:
            questions.append(
                {
                    "stage": "sampling_design",
                    "question": f"Il dominio {domain['domain_id']} deve proiettarsi su gateway, plc4j o entrambi?",
                    "why": "La proiezione di trasporto serve per generare richieste runtime coerenti.",
                }
            )
    if questions:
        return {"stage": stage, "questions": questions}

    stage = "transport_architecture"
    transport = model["transport_architecture"]
    if not transport["primary_transport_mode"]:
        questions.append(
            {
                "stage": "transport_architecture",
                "question": "L'applicazione usa moqui-device-gateway, moqui-plc4j o una proiezione ibrida?",
                "why": "Almeno un transport layer reale deve essere modellato prima della generazione completa.",
            }
        )
    if transport["gateway_required"] and not any(
        row["gateway_device_id"] for row in model["gateways"]
    ):
        questions.append(
            {
                "stage": "transport_architecture",
                "question": "Qual e l'identita del gateway e quali sottosistemi o device ricadono nel suo scope?",
                "why": "Serve per generare Device, PhysicalDevice e DeviceGroupMember del gateway.",
            }
        )
    if transport["plc4j_required"] and not any(
        row["connection_name"] for row in model["plc4j_connections"]
    ):
        questions.append(
            {
                "stage": "transport_architecture",
                "question": "Quali connessioni plc4j servono e a quali domini di campionamento si applicano?",
                "why": "DeviceConnection e runServiceName dipendono da questa risposta.",
            }
        )
    if questions:
        return {"stage": stage, "questions": questions}

    stage = "main_fsm"
    questions.append(
        {
            "stage": "main_fsm",
            "question": "I dati upstream sono completi: ora puoi definire stati, alfabeto I/O e transizioni del Main / MainRuleEngine in termini di atomic component.",
            "why": "Solo adesso e corretto passare dall'ingegneria di sistema ai template FSM.",
        }
    )
    return {"stage": stage, "questions": questions}


def render_markdown(summary: dict) -> str:
    lines = ["# Guided Questions", "", f"Next stage: `{summary['stage']}`", ""]
    for index, item in enumerate(summary["questions"], start=1):
        lines.append(f"{index}. [{item['stage']}] {item['question']}")
        lines.append(f"   Why: {item['why']}")
    lines.append("")
    return "\n".join(lines)


def update_session(session_dir: Path, output_path: Path, stage: str) -> None:
    session_path, session = load_session(session_dir)
    artifacts = session.setdefault("artifacts", {})
    rel_output = str(output_path.relative_to(session_dir))
    generated = artifacts.setdefault("generatedConfig", [])
    if rel_output not in generated:
        generated.append(rel_output)
    session["updatedAt"] = utc_now()
    session["currentStage"] = stage
    session["currentSkill"] = "moqui-plant-designer"
    session_path.write_text(json.dumps(session, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Render model-driven guided questions from the current plant-design session")
    parser.add_argument("--session-dir", type=Path, required=True, help="Saved session directory")
    parser.add_argument("--output", type=Path, help="Optional Markdown output path")
    parser.add_argument("--json", action="store_true", help="Print JSON summary instead of Markdown")
    args = parser.parse_args()

    session_dir = args.session_dir.resolve()
    load_session(session_dir)
    model = load_upstream_survey_model(session_dir)
    atomic_library = load_atomic_library()
    summary = build_guided_questions(model, atomic_library)

    if args.json:
        print(json.dumps(summary, indent=2))
        return 0

    output_path = args.output or session_dir / "notes" / "guided-questions.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown(summary), encoding="utf-8")
    update_session(session_dir, output_path, summary["stage"])
    print(f"Wrote guided questions to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

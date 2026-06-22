from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


@dataclass
class TransformResult:
    text: str
    applied: list[str] = field(default_factory=list)


REFERENCE_TO_RE = re.compile(r"\bREFERENCE\s+TO\b")
MC_DIRECTION_RE = re.compile(r"\bMC_DIRECTION\b")

# CODESYS motion namespace → AX compat namespace substitutions.
# Applied mechanically to all files; matches are scoped to motion files by the prefixes used.
MOTION_NAMESPACE_REPLACEMENTS: list[tuple[str, str]] = [
    ("SM3_Robotics.SMC_COORD_SYSTEM", "CoordMotion.SMC_COORD_SYSTEM"),
    ("SM3_Robotics.MC_TRANSITION_MODE", "CoordMotion.MC_TRANSITION_MODE"),
    ("SM3_Robotics.SMC_POS_REF", "CoordMotion.SMC_POS_REF"),
    ("SM3_Robotics.SMC_CIRC_MODE", "CoordMotion.SMC_CIRC_MODE"),
    ("SM3_Robotics.MC_CIRC_PATHCHOICE", "CoordMotion.MC_CIRC_PATHCHOICE"),
    ("SM3_Robotics.AXIS_GROUP_REF_SM3", "TO_Kinematics"),
    ("SM3_Basic.MC_BUFFER_MODE", "Motion.MC_BUFFER_MODE"),
]
CONTROL_END_RE = re.compile(r"\b(END_IF|END_CASE|END_FOR|END_WHILE|END_REPEAT)\b(?!\s*;)")
REF_ASSIGN_RE = re.compile(
    r"(?P<indent>^[ \t]*)(?P<lhs>[A-Za-z_][A-Za-z0-9_\.\[\]]*)\s+REF=\s+(?P<rhs>[^;\r\n]+);",
    re.MULTILINE,
)
ATTRIBUTE_LINE_RE = re.compile(r"^(?P<indent>[ \t]*)\{attribute\s+'(?P<name>[^']+)'\}(?P<eol>\n|$)", re.MULTILINE)
ENUM_BLOCK_RE = re.compile(
    r"(?P<prefix>\bTYPE\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*:\s*\()"
    r"(?P<body>.*?)"
    r"(?P<suffix>\)\s*(?:[A-Za-z_][A-Za-z0-9_]*\s*)?;\s*END_TYPE)",
    re.DOTALL,
)
ENUM_MEMBER_VALUE_RE = re.compile(r"(?P<member>\b[A-Za-z_][A-Za-z0-9_]*\b)(?P<ws>\s*):=(?P<after>\s*)(?P<value>[^,\r\n)]+)")
TYPE_UNION_RE = re.compile(r"\b(TYPE\s+[A-Za-z_][A-Za-z0-9_]*\s*:\s*)UNION\b")
END_UNION_RE = re.compile(r"\bEND_UNION\b")
END_STRUCT_END_TYPE_RE = re.compile(r"\bEND_STRUCT(?P<ws>\s+)END_TYPE\b")
DECLARATION_SEPARATOR_RE = re.compile(
    r"^[ \t]*\(\*#-#-#-#-#-#-#-#-#-#---Declaration---#-#-#-#-#-#-#-#-#-#-#-#-#\*\)[ \t]*(?:\n|$)",
    re.IGNORECASE | re.MULTILINE,
)
IMPLEMENTATION_SEPARATOR_RE = re.compile(
    r"^[ \t]*\(\*#-#-#-#-#-#-#-#-#-#---Implementation---#-#-#-#-#-#-#-#-#-#-#-#-#\*\)[ \t]*(?:\n|$)",
    re.IGNORECASE | re.MULTILINE,
)


def normalize_line_endings(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _apply(result: TransformResult, name: str, fn) -> None:
    new_text, count = fn(result.text)
    if count:
        result.text = new_text
        result.applied.append(name)


def remove_export_separators(text: str) -> tuple[str, int]:
    text, first = DECLARATION_SEPARATOR_RE.subn("", text)
    text, second = IMPLEMENTATION_SEPARATOR_RE.subn("", text)
    return text, first + second


def convert_attributes(text: str) -> tuple[str, int]:
    def repl(match: re.Match[str]) -> str:
        return (
            f"{match.group('indent')}(* AX_TODO: removed CODESYS attribute "
            f"'{match.group('name')}'. *){match.group('eol')}"
        )

    return ATTRIBUTE_LINE_RE.subn(repl, text)


def remove_explicit_enum_values(text: str) -> tuple[str, int]:
    changed = 0

    def block_repl(match: re.Match[str]) -> str:
        nonlocal changed
        body, count = ENUM_MEMBER_VALUE_RE.subn(lambda m: m.group("member"), match.group("body"))
        changed += count
        return match.group("prefix") + body + match.group("suffix")

    return ENUM_BLOCK_RE.sub(block_repl, text), changed


def convert_ref_assignments(text: str) -> tuple[str, int]:
    def repl(match: re.Match[str]) -> str:
        return f"{match.group('indent')}{match.group('lhs')} := REF({match.group('rhs').strip()});"

    return REF_ASSIGN_RE.subn(repl, text)


def convert_unions(text: str) -> tuple[str, int]:
    text, first = TYPE_UNION_RE.subn(r"\1STRUCT", text)
    text, second = END_UNION_RE.subn("END_STRUCT", text)
    return text, first + second


def normalize_type_endings(text: str) -> tuple[str, int]:
    return END_STRUCT_END_TYPE_RE.subn(lambda m: f"END_STRUCT;{m.group('ws')}END_TYPE", text)


def flatten_nested_comments(text: str) -> tuple[str, int]:
    output: list[str] = []
    i = 0
    in_comment = False
    nested_depth = 0
    changes = 0
    while i < len(text):
        pair = text[i:i + 2]
        if not in_comment:
            if pair == "(*":
                in_comment = True
                output.append(pair)
                i += 2
            else:
                output.append(text[i])
                i += 1
            continue
        if pair == "(*":
            nested_depth += 1
            output.append("[")
            changes += 1
            i += 2
            continue
        if pair == "*)":
            if nested_depth:
                nested_depth -= 1
                output.append("]")
                changes += 1
            else:
                in_comment = False
                output.append(pair)
            i += 2
            continue
        output.append(text[i])
        i += 1
    return "".join(output), changes


def convert_enum_access(text: str, enum_type_names: Iterable[str]) -> tuple[str, int]:
    total = 0
    for enum_name in sorted(set(enum_type_names), key=len, reverse=True):
        text, count = re.subn(
            rf"\b{re.escape(enum_name)}\.([A-Za-z_][A-Za-z0-9_]*)\b",
            rf"{enum_name}#\1",
            text,
        )
        total += count
    return text, total


def convert_motion_namespaces(text: str) -> tuple[str, int]:
    count = 0
    for source, target in MOTION_NAMESPACE_REPLACEMENTS:
        if source in text:
            text = text.replace(source, target)
            count += 1
    return text, count


def ensure_final_newline(text: str) -> str:
    return text if not text or text.endswith("\n") else text + "\n"


def convert_text(relative: Path, source_text: str, enum_type_names: Iterable[str]) -> TransformResult:
    """Apply only registered AX syntax/compatibility transformations.

    The transformer deliberately preserves comments, indentation, blank lines and
    declaration order. It never calls strip/rstrip on the complete source.
    """
    result = TransformResult(text=normalize_line_endings(source_text))
    _apply(result, "remove_export_separators", remove_export_separators)
    _apply(result, "remove_codesys_attributes", convert_attributes)
    _apply(result, "remove_explicit_enum_values", remove_explicit_enum_values)
    _apply(result, "convert_ref_assignments", convert_ref_assignments)
    _apply(result, "convert_union_to_struct", convert_unions)
    _apply(result, "normalize_type_endings", normalize_type_endings)
    _apply(result, "normalize_control_endings", lambda t: CONTROL_END_RE.subn(r"\1;", t))
    _apply(result, "flatten_nested_comments", flatten_nested_comments)
    _apply(result, "convert_enum_access", lambda t: convert_enum_access(t, enum_type_names))
    _apply(result, "reference_to_to_ref_to", lambda t: REFERENCE_TO_RE.subn("REF_TO", t))
    _apply(result, "normalize_mc_direction", lambda t: MC_DIRECTION_RE.subn("MC_Direction", t))
    _apply(result, "convert_motion_namespaces", convert_motion_namespaces)
    result.text = ensure_final_newline(result.text)
    return result

"""Rewrite the canonical CODESYS-flavoured ST tree for open-source ST compilers.

The rewrites are mechanical and apply to code only: comments, pragmas and
string literals are never changed (see codesys_namespaces.split_code). The
canonical tree is the source of truth; compile-st.py runs these rewrites on a
copy under codegen/target/<target>/.

Rewrites, in order:

1. ``LIB.NAME`` that would collide once namespaces are dropped gets a
   prefixed name (``JSON.ERROR`` -> ``JSON_ERROR``).
2. CODESYS library namespaces and library parameter lists are dropped
   (``MQTT.MQTTClient`` -> ``MQTTClient``).
3. Qualifiers of global variable lists are dropped (``ec.init`` -> ``init``):
   standard ST has no named global variable lists.
4. ``UNION`` becomes ``STRUCT``. Member access and types are the same; the
   members no longer share memory. No caller in moqui-plc relies on the
   overlay (LogPayload carries a type tag).
5. RuSTy only: ``__ISVALIDREF(r)`` becomes ``(ADR(r) <> 0)`` (an unbound
   reference has address 0) and the CODESYS ``__UXINT_TO_<T>`` conversions
   become ``TO_<T>``.
6. ``__XADD(p, v)`` becomes ``MOQUI_XADD(p, v)``: neither compiler has the
   CODESYS atomic operators; rust-plc/interfaces/codesys-system/atomic.st
   declares the function a runtime implements as an atomic fetch-add.
7. IronPLC only: nested comments are flattened and enumeration qualifiers are
   dropped (``MainStatus.Idle`` -> ``Idle``), because IronPLC resolves
   enumeration values from context and rejects the qualified form inside
   statements. CONFIGURATION files get TASK lines before PROGRAM lines.
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Iterable

from codesys_namespaces import split_code

IDENT = r"[A-Za-z_][A-Za-z0-9_]*"
_TYPE_ENUM_RE = re.compile(r"\bTYPE\s+(" + IDENT + r")\s*:\s*\(", re.IGNORECASE)
_VAR_GLOBAL_HEAD_RE = re.compile(r"\s*VAR_GLOBAL\b", re.IGNORECASE)
_UNION_RE = re.compile(r"(?<![A-Za-z0-9_])UNION(?![A-Za-z0-9_])")
_ISVALIDREF_RE = re.compile(r"__ISVALIDREF\s*\(\s*([A-Za-z_][A-Za-z0-9_.\[\]]*)\s*\)", re.IGNORECASE)
_UXINT_TO_RE = re.compile(r"(?<![A-Za-z0-9_])__UXINT_TO_(?=[A-Za-z])", re.IGNORECASE)
_END_UNION_RE = re.compile(r"(?<![A-Za-z0-9_])END_UNION(?![A-Za-z0-9_])")
_XADD_RE = re.compile(r"(?<![A-Za-z0-9_])__XADD(?=\s*\()", re.IGNORECASE)


def code_only(text: str) -> str:
    """Return text with every comment, pragma and string replaced by spaces."""
    return "".join(segment if is_code else re.sub(r"[^\n]", " ", segment) for is_code, segment in split_code(text))


def _sub_code(text: str, regex: re.Pattern, repl, counter: Counter, key: str) -> str:
    parts = []
    for is_code, segment in split_code(text):
        if is_code:
            segment, count = regex.subn(repl, segment)
            counter[key] += count
        parts.append(segment)
    return "".join(parts)


def _alternation(names: Iterable[str]) -> str:
    return "|".join(re.escape(n) for n in sorted(set(names), key=len, reverse=True))


def flatten_nested_comments(text: str) -> str:
    """Turn inner ``(* *)`` pairs into ``[ ]`` so only one comment level remains."""
    out, index, depth, in_string = [], 0, 0, ""
    while index < len(text):
        char, pair = text[index], text[index : index + 2]
        if depth == 0 and in_string:
            out.append(char)
            if char == "$":
                out.append(text[index + 1 : index + 2])
                index += 2
                continue
            if char == in_string:
                in_string = ""
            index += 1
        elif depth == 0 and char in "'\"":
            in_string = char
            out.append(char)
            index += 1
        elif pair == "(*":
            out.append("(*" if depth == 0 else "[")
            depth += 1
            index += 2
        elif pair == "*)" and depth:
            depth -= 1
            out.append("*)" if depth == 0 else "]")
            index += 2
        else:
            out.append(char)
            index += 1
    return "".join(out)


def reorder_configuration(text: str) -> str:
    """Put TASK declarations right after RESOURCE, before PROGRAM instances."""
    lines = text.split("\n")
    tasks = [line for line in lines if line.strip().upper().startswith("TASK ")]
    out = []
    for line in lines:
        if line.strip().upper().startswith("TASK "):
            continue
        out.append(line)
        if line.strip().upper().startswith("RESOURCE "):
            out.extend(tasks)
    return "\n".join(out)


def global_variable_lists(texts: dict[Path, str]) -> list[str]:
    """Files whose code starts with VAR_GLOBAL are CODESYS global variable lists."""
    return sorted(path.stem for path, text in texts.items() if _VAR_GLOBAL_HEAD_RE.match(code_only(text)))


def enumeration_types(texts: Iterable[str]) -> list[str]:
    names = set()
    for text in texts:
        names.update(_TYPE_ENUM_RE.findall(code_only(text)))
    return sorted(names)


class DialectRewriter:
    def __init__(
        self,
        target: str,
        namespaces: Iterable[str],
        renamed: dict[str, str],
        parameter_lists: Iterable[str],
        global_lists: Iterable[str],
        enumerations: Iterable[str],
    ) -> None:
        self.target = target
        self.counts: Counter = Counter()
        self._renamed = [
            (re.compile(r"(?<![A-Za-z0-9_.])" + re.escape(old) + r"(?![A-Za-z0-9_])"), new) for old, new in sorted(renamed.items())
        ]
        self._namespace_re = re.compile(r"(?<![A-Za-z0-9_.])(?:" + _alternation(namespaces) + r")\.(?=[A-Za-z_])")
        params = list(parameter_lists)
        self._param_re = re.compile(r"(?<![A-Za-z0-9_.])(?:" + _alternation(params) + r")\.(?=[A-Za-z_])") if params else None
        gvls = list(global_lists)
        self._gvl_re = re.compile(r"(?<![A-Za-z0-9_.])(?:" + _alternation(gvls) + r")\.(?=[A-Za-z_])") if gvls else None
        enums = list(enumerations)
        self._enum_re = (
            re.compile(r"(?<![A-Za-z0-9_.])(?:" + _alternation(enums) + r")\.(" + IDENT + r")", re.IGNORECASE) if enums else None
        )

    def rewrite(self, text: str, file_name: str = "") -> str:
        counts = self.counts
        if self.target == "ironplc":
            flattened = flatten_nested_comments(text)
            counts["nested comments flattened"] += int(flattened != text)
            text = flattened
        for regex, new in self._renamed:
            text = _sub_code(text, regex, new, counts, "colliding library names renamed")
        previous = None
        while previous != text:
            previous = text
            text = _sub_code(text, self._namespace_re, "", counts, "library namespace qualifiers dropped")
        if self._param_re:
            text = _sub_code(text, self._param_re, "", counts, "library parameter list qualifiers dropped")
        if self._gvl_re:
            text = _sub_code(text, self._gvl_re, "", counts, "global variable list qualifiers dropped")
        text = _sub_code(text, _END_UNION_RE, "END_STRUCT", counts, "UNION declared as STRUCT")
        text = _sub_code(text, _UNION_RE, "STRUCT", counts, "UNION declared as STRUCT")
        text = _sub_code(text, _XADD_RE, "MOQUI_XADD", counts, "__XADD written as MOQUI_XADD")
        if self.target == "rusty":
            text = _sub_code(text, _ISVALIDREF_RE, r"(ADR(\1) <> 0)", counts, "__ISVALIDREF written as ADR(...) <> 0")
            text = _sub_code(text, _UXINT_TO_RE, "TO_", counts, "__UXINT_TO_ conversions written as TO_")
        if self.target == "ironplc":
            if self._enum_re:
                text = _sub_code(text, self._enum_re, lambda m: m.group(1), counts, "enumeration qualifiers dropped")
            if re.search(r"(?m)^\s*CONFIGURATION\b", code_only(text)):
                reordered = reorder_configuration(text)
                counts["configuration TASK lines moved"] += int(reordered != text)
                text = reordered
        return text

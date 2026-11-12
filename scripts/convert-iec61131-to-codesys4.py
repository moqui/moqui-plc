#!/usr/bin/env python3
"""Generate the CODESYS 4 application of moqui-plc from the canonical iec61131 tree.

The canonical tree (iec61131/) is never modified. This script writes, under the application folder of the CODESYS 4
project (codesys-v4/moqui-plc.fbsdev/moqui.iecapp^/):

- moqui/: one object file per POU, type and global variable list, in the folders of the canonical tree, named with
  the CODESYS 4 suffix of its kind (.prg.st, .fb.st, .fn.st, .struct, .enum, .union, .alias, .gvl, .itf);
- TaskConfiguration.json: the tasks of iec61131/configuration.st, only CODESYS4_ENABLED_TASKS active, the others
  commented out;
- Libraries.json: the library references and the placeholder resolutions the SoftMotion libraries need.

What CODESYS 4 requires and the canonical (CODESYS 3.5) code does not do:

- A global variable list is a NAMESPACE named after the list, and its variables are reachable only qualified
  (ec.dev, MoquiConf.brokerUrl). USING is not supported. Every unqualified use of a global variable is qualified,
  unless a local declaration of the same name hides it; VAR_EXTERNAL declarations of global variables are removed.
- SoftMotion symbols carry their library namespace (SM3_Basic., SM3_Robotics.), as in the CODESYS 3.5 project
  (scripts/codesys_namespaces.py).
- The text before the first keyword, such as a UTF-8 byte order mark, is dropped.
- The objects that CODESYS 3.5 generates from the device tree (drives, axis groups, cam table) are declared in the
  global variable list deviceTree (moqui/deviceTree.gvl), from rust-plc/interfaces/device-tree/DeviceTree.st.
- The objects of CODESYS4_EXCLUDED_OBJECTS (NetworkDiagnostics) are left out, with the variables of their type.

See codesys-v4/README.md.

The libraries that CODESYS 4 does not ship (SoftMotion and its dependencies, Recipe Management) are installed into a
local library repository from the CODESYS 3.5 project archive with --install-libraries.

Usage (from the repository root):
    python3 scripts/convert-iec61131-to-codesys4.py              generate the application
    python3 scripts/convert-iec61131-to-codesys4.py --build      generate, resolve the libraries and compile
    python3 scripts/convert-iec61131-to-codesys4.py --install-libraries
                                                                 install the missing libraries, then generate
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import moqui_plc_config as config  # noqa: E402
from codesys_namespaces import split_code, to_codesys  # noqa: E402

REPO_ROOT = Path(config.REPO_ROOT)
CANONICAL_ROOT = Path(config.IEC61131_MOQUI_ROOT)
CONFIGURATION_FILE = Path(config.IEC61131_ROOT) / "configuration.st"
APPLICATION = REPO_ROOT / config.CODESYS4_APPLICATION
APPLICATION_DIR = Path(str(APPLICATION) + "^")
GENERATED_DIR = APPLICATION_DIR / config.CODESYS4_SOURCE_FOLDER
C4_CLI = os.environ.get("MOQUI_PLC_C4_CLI", config.CODESYS4_CLI)

IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
VAR_BLOCK = re.compile(r"\b(VAR(?:_INPUT|_OUTPUT|_IN_OUT|_GLOBAL|_EXTERNAL|_TEMP|_STAT|_INST|_CONFIG)?)\b(.*?)\bEND_VAR\b", re.S)
STRUCT_BLOCK = re.compile(r"\bSTRUCT\b(.*?)\bEND_STRUCT\b", re.S)


# ---------------------------------------------------------------------------
# Source objects
# ---------------------------------------------------------------------------


@dataclass
class SourceObject:
    path: Path  # relative to the canonical tree
    text: str
    kind: str = ""  # prg, fb, fn, struct, enum, union, alias, gvl, itf
    name: str = ""
    extends: str = ""
    declared: set = field(default_factory=set)  # lower-case names declared in the object
    converted: bool = False  # the text already has the CODESYS library qualifiers

    @property
    def suffix(self) -> str:
        return {"prg": ".prg.st", "fb": ".fb.st", "fn": ".fn.st"}.get(self.kind, "." + self.kind)


def code_only(text: str) -> str:
    """The text with comments, pragmas and string literals blanked, positions kept."""
    return "".join(seg if is_code else " " * len(seg) for is_code, seg in split_code(text))


def strip_preamble(text: str) -> str:
    """Drop a UTF-8 byte order mark."""
    return text[1:] if text.startswith("﻿") else text


def classify(obj: SourceObject) -> None:
    code = code_only(obj.text)
    match = re.search(
        r"\b(PROGRAM|FUNCTION_BLOCK|FUNCTION|TYPE|VAR_GLOBAL|INTERFACE)\b"
        r"(?:\s+(?:PUBLIC|INTERNAL|FINAL|ABSTRACT))*\s*([A-Za-z_][A-Za-z0-9_]*)?",
        code,
    )
    if not match:
        raise ValueError("%s: no POU, type or global variable list found" % obj.path)
    keyword, name = match.group(1), match.group(2)
    obj.name = obj.path.stem
    if keyword == "PROGRAM":
        obj.kind = "prg"
    elif keyword == "FUNCTION_BLOCK":
        obj.kind = "fb"
        extends = re.search(r"\bEXTENDS\s+([A-Za-z_][A-Za-z0-9_.]*)", code[match.end():].split("\n", 1)[0])
        obj.extends = extends.group(1) if extends else ""
    elif keyword == "FUNCTION":
        obj.kind = "fn"
    elif keyword == "INTERFACE":
        obj.kind = "itf"
    elif keyword == "VAR_GLOBAL":
        obj.kind = "gvl"
    else:
        body = code[match.end():].split("END_TYPE", 1)[0]
        if re.search(r"\bSTRUCT\b", body):
            obj.kind = "struct"
        elif re.search(r"\bUNION\b", body):
            obj.kind = "union"
        elif re.match(r"\s*(?:EXTENDS\s+\S+\s*)?:\s*(?:[A-Za-z_][A-Za-z0-9_]*\s*)?\(", body):
            obj.kind = "enum"
        else:
            obj.kind = "alias"
    if name and keyword != "VAR_GLOBAL" and name.lower() != obj.name.lower():
        raise ValueError("%s declares %s: the file must be named after the object" % (obj.path, name))
    obj.declared = declared_names(code)


QUALIFIERS = re.compile(r"^\s*(?:(?:CONSTANT|RETAIN|PERSISTENT|NON_RETAIN)\s+)*")


def declared_names(code: str) -> set:
    """Lower-case names declared in the VAR and STRUCT blocks of code-only text.

    VAR_EXTERNAL blocks are left out: they name global variables, they do not declare local ones.
    """
    names = set()
    blocks = [m.group(2) for m in VAR_BLOCK.finditer(code) if m.group(1) != "VAR_EXTERNAL"]
    blocks += [m.group(1) for m in STRUCT_BLOCK.finditer(code)]
    for block in blocks:
        block = QUALIFIERS.sub("", block)
        for statement in block.split(";"):
            head = re.split(r"(?<!:):(?!=)", statement, maxsplit=1)
            if len(head) < 2:
                continue
            head = re.sub(r"\bAT\s+%\S+", "", head[0])
            for candidate in head.split(","):
                candidate = candidate.strip()
                if IDENTIFIER.fullmatch(candidate):
                    names.add(candidate.lower())
    return names


def load_objects() -> list[SourceObject]:
    objects = []
    excluded = {name.lower() for name in config.CODESYS4_EXCLUDED_OBJECTS}
    for path in sorted(CANONICAL_ROOT.rglob("*.st")):
        if path.stem.lower() in excluded:
            continue
        text = strip_preamble(path.read_text(encoding="utf-8"))
        for name in config.CODESYS4_EXCLUDED_OBJECTS:
            text = drop_declarations(text, r"[A-Za-z_][A-Za-z0-9_]*", name)
        obj = SourceObject(path.relative_to(CANONICAL_ROOT), text)
        classify(obj)
        objects.append(obj)
    objects.append(device_tree())
    return objects


def drop_declarations(text: str, variable: str, type_name: str = r"[^;\n]+") -> str:
    """Remove the one-line declarations of variable (a regular expression) with type type_name, together with the
    comment line right above them."""
    return re.sub(r"(?im)(?:^[ \t]*\(\*[^\n]*\*\)[ \t]*\n(?=[ \t]*(?:%s)[ \t]*:))?^[ \t]*(?:%s)[ \t]*:[ \t]*%s[ \t]*;[^\n]*\n(?:[ \t]*\n(?=[ \t]*\n))?"
                  % (variable, variable, type_name), "", text)


def device_tree() -> SourceObject:
    """The device-tree objects as the global variable list config.CODESYS4_DEVICE_TREE_LIST, without the excluded
    objects and with the CODESYS 4 types of config.CODESYS4_DEVICE_TREE_TYPES."""
    text = (REPO_ROOT / config.CODESYS4_DEVICE_TREE).read_text(encoding="utf-8")
    for name in config.CODESYS4_DEVICE_TREE_EXCLUDED:
        text = drop_declarations(text, re.escape(name))
    text = re.sub(r"(\bVAR_GLOBAL[ \t]*\n)[ \t]*\n", r"\1", text)
    text = to_codesys(text)
    for name, replacement in config.CODESYS4_DEVICE_TREE_TYPES.items():
        text = re.sub(r"(?<![\w.])%s\b" % re.escape(name), replacement, text)
    obj = SourceObject(Path(config.CODESYS4_DEVICE_TREE_LIST + ".st"), text, converted=True)
    classify(obj)
    return obj


# ---------------------------------------------------------------------------
# Global variables
# ---------------------------------------------------------------------------


def global_variables(objects: list[SourceObject]) -> dict:
    """Lower-case variable name -> name of its global variable list."""
    owners = {}
    for obj in objects:
        if obj.kind != "gvl":
            continue
        for name in obj.declared:
            if name in owners:
                raise ValueError("Global variable %s is declared in %s and %s" % (name, owners[name], obj.name))
            owners[name] = obj.name
    return owners


def inherited_names(obj: SourceObject, by_name: dict) -> set:
    """The names declared by a function block and the function blocks it extends."""
    names = set(obj.declared)
    seen = set()
    parent = obj.extends
    while parent and parent.lower() in by_name and parent.lower() not in seen:
        seen.add(parent.lower())
        base = by_name[parent.lower()]
        names |= base.declared
        parent = base.extends
    return names


TYPE_CONTEXT = re.compile(r"\b(?:TYPE|OF|TO|EXTENDS|IMPLEMENTS)\s*$", re.IGNORECASE)


def qualify_globals(text: str, owners: dict, hidden: set, own_list: str = "", types: set = frozenset()) -> str:
    """Prefix each unqualified use of a global variable with its list name.

    Skipped: names hidden by a local declaration, member accesses (a.name), enumeration and typed literals
    (Type#value), named call arguments (f(name := x), f(name => y)), the variables of the list itself and
    type names in a type position (TYPE name, x : name, ARRAY OF name, REFERENCE TO name, EXTENDS name).
    """
    out = []
    depth = 0
    pending = [(is_code, seg) for is_code, seg in split_code(text)]
    flat = "".join(seg if is_code else " " * len(seg) for is_code, seg in pending)
    position = 0
    for is_code, segment in pending:
        if not is_code:
            out.append(segment)
            position += len(segment)
            continue
        result = []
        last = 0
        for match in re.finditer(r"[()]|[A-Za-z_][A-Za-z0-9_]*", segment):
            token = match.group(0)
            if token == "(":
                depth += 1
                continue
            if token == ")":
                depth = max(0, depth - 1)
                continue
            owner = owners.get(token.lower())
            if not owner or owner == own_list or token.lower() in hidden:
                continue
            i = position + match.start() - 1
            while i >= 0 and flat[i].isspace():
                i -= 1
            # a.name and Type#value are not global variables; a range bound (1..name) is
            if i >= 0 and (flat[i] == "#" or (flat[i] == "." and (i == 0 or flat[i - 1] != "."))):
                continue
            j = position + match.end()
            while j < len(flat) and flat[j].isspace():
                j += 1
            if depth > 0 and flat[j:j + 2] in (":=", "=>"):
                continue
            # a variable may share its (case-insensitive) name with a type: workEffort : WorkEffort
            if token.lower() in types and i >= 0 and (flat[i] == ":" or TYPE_CONTEXT.search(flat[max(0, i - 16):i + 1])):
                continue
            result.append(segment[last:match.start()])
            result.append(owner + "." + token)
            last = match.end()
        result.append(segment[last:])
        out.append("".join(result))
        position += len(segment)
    return "".join(out)


def drop_external_globals(text: str, owners: dict) -> str:
    """Remove VAR_EXTERNAL declarations of global variables, and the blocks left empty."""

    def block(match):
        body = match.group(1)
        kept = []
        for line in body.split("\n"):
            code = code_only(line)
            declared = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*(?:\s*,\s*[A-Za-z_][A-Za-z0-9_]*)*)\s*:(?!=)", code)
            if declared and all(n.strip().lower() in owners for n in declared.group(1).split(",")):
                continue
            kept.append(line)
        remaining = QUALIFIERS.sub("", "".join(code_only(line) for line in kept))
        if not remaining.strip():
            return ""
        return "VAR_EXTERNAL" + "\n".join(kept) + "END_VAR"

    result = re.sub(r"\bVAR_EXTERNAL\b(.*?)\bEND_VAR\b", block, text, flags=re.S)
    return re.sub(r"\n[ \t]*\n(?=[ \t]*\n)", "\n", result)


def wrap_global_list(obj: SourceObject, text: str) -> str:
    """A CODESYS 4 global variable list: the declarations inside NAMESPACE <list name>."""
    return "NAMESPACE %s\n%s%sEND_NAMESPACE\n" % (obj.name, text, "" if text.endswith("\n") else "\n")


def convert(obj: SourceObject, owners: dict, by_name: dict) -> str:
    text = obj.text if obj.converted else to_codesys(obj.text)
    if obj.kind == "enum":
        return text
    hidden = inherited_names(obj, by_name) if obj.kind == "fb" else set(obj.declared)
    if obj.kind == "gvl":
        hidden = set()
    text = drop_external_globals(text, owners)
    types = {name for name, other in by_name.items() if other.kind not in ("prg", "fn", "gvl")}
    text = qualify_globals(text, owners, hidden, obj.name if obj.kind == "gvl" else "", types)
    if obj.kind == "gvl":
        text = wrap_global_list(obj, text)
    return text


# ---------------------------------------------------------------------------
# Tasks and libraries
# ---------------------------------------------------------------------------


def parse_time_us(value: str) -> int:
    """Microseconds of an IEC TIME literal such as T#10ms or TIME#1s500ms."""
    body = value.split("#", 1)[1].lower().replace("_", "")
    units = {"d": 86400e6, "h": 3600e6, "m": 60e6, "s": 1e6, "ms": 1e3, "us": 1.0, "ns": 1e-3}
    total = 0.0
    for number, unit in re.findall(r"(\d+(?:\.\d+)?)(ms|us|ns|d|h|m|s)", body):
        total += float(number) * units[unit]
    return int(round(total))


def task_configuration(text: str) -> str:
    """TaskConfiguration.json from the TASK and PROGRAM ... WITH declarations of configuration.st.

    The tasks of config.CODESYS4_ENABLED_TASKS are active; the others are written as comments, which CODESYS 4
    accepts in its JSON files.
    """
    tasks = {}
    kind = "Cyclic"
    for line in text.splitlines():
        comment = re.search(r"Kind:\s*(\w+)", line)
        if comment:
            kind = comment.group(1)
            continue
        task = re.match(r"\s*TASK\s+(\w+)\s*\(\s*INTERVAL\s*:=\s*([^,\s)]+)\s*,\s*PRIORITY\s*:=\s*(\d+)\s*\)\s*;", line)
        if task:
            tasks[task.group(1)] = {
                "calls": [],
                "priority": int(task.group(3)),
                "type": kind,
                "interval": parse_time_us(task.group(2)),
                "watchdogEnable": False,
                "watchdogTime": 0,
                "watchdogSensitivity": 0,
            }
            kind = "Cyclic"
            continue
        program = re.match(r"\s*PROGRAM\s+\w+\s+WITH\s+(\w+)\s*:\s*(\w+)\s*;", line)
        if program:
            tasks[program.group(1)]["calls"].append(program.group(2))
    missing = set(config.CODESYS4_ENABLED_TASKS) - set(tasks)
    if missing:
        raise ValueError("CODESYS4_ENABLED_TASKS names tasks missing from configuration.st: %s" % ", ".join(sorted(missing)))
    indent = "\t" * 4
    enabled = [name for name in tasks if name in config.CODESYS4_ENABLED_TASKS]
    entries = []
    for name, task in tasks.items():
        body = json.dumps({name: task}, indent="\t")[1:-1].strip("\n").replace("\n\t", "\n" + indent)
        body = indent + body.lstrip("\t")
        if name in enabled:
            entries.append(body + ("," if name != enabled[-1] else ""))
        else:
            entries.append("\n".join(line[:len(indent)] + "// " + line[len(indent):] + ("," if i == body.count("\n") else "")
                                     for i, line in enumerate(body.split("\n"))))
    return ('{\n\t"taskGroups": [\n\t\t{\n\t\t\t"groupName": "IEC-Tasks",\n\t\t\t"tasks": {\n%s\n\t\t\t},\n'
            '\t\t\t"coreConfig": "FixedPinned"\n\t\t}\n\t],\n\t"systemEvents": []\n}\n' % "\n".join(entries))


def libraries() -> dict:
    references = {"Standard": {"$type": "Placeholder", "placeholder": "Standard"}}
    for namespace, library in config.CODESYS4_LIBRARIES.items():
        references[namespace] = {"$type": "ManagedLibrary", "libraryId": library}
        if namespace in config.CODESYS4_UNQUALIFIED_LIBRARIES:
            references[namespace]["allowUnqualifiedAccess"] = True
    return {
        "references": references,
        "placeholderOverrides": dict(sorted(config.CODESYS4_PLACEHOLDER_OVERRIDES.items())),
        "libraryParameters": {},
    }


def set_bus_cycle_task() -> None:
    """Point the I/O bus cycle of the device at a task of the generated configuration."""
    device = REPO_ROOT / config.CODESYS4_DEVICE
    data = json.loads(device.read_text(encoding="utf-8"))
    plc = data["extensions"]["BaseDevice.PlcConfig"]["configuration"]
    if plc.get("busCycleTask") != config.CODESYS4_BUS_CYCLE_TASK:
        plc["busCycleTask"] = config.CODESYS4_BUS_CYCLE_TASK
        write_json(device, data)


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent="\t") + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def generate() -> int:
    objects = load_objects()
    owners = global_variables(objects)
    by_name = {obj.name.lower(): obj for obj in objects}
    if GENERATED_DIR.exists():
        shutil.rmtree(GENERATED_DIR)
    for obj in objects:
        target = GENERATED_DIR / obj.path.parent / (obj.name + obj.suffix)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(convert(obj, owners, by_name), encoding="utf-8")
    (APPLICATION_DIR / "TaskConfiguration.json").write_text(
        task_configuration(CONFIGURATION_FILE.read_text(encoding="utf-8")), encoding="utf-8")
    write_json(APPLICATION_DIR / "Libraries.json", libraries())
    for placeholder in config.CODESYS4_REMOVED_OBJECTS:
        (APPLICATION_DIR / placeholder).unlink(missing_ok=True)
    set_bus_cycle_task()
    kinds = {}
    for obj in objects:
        kinds[obj.suffix] = kinds.get(obj.suffix, 0) + 1
    print("Generated %d objects in %s: %s" % (len(objects), GENERATED_DIR.relative_to(REPO_ROOT),
                                              ", ".join("%d %s" % (n, k) for k, n in sorted(kinds.items()))))
    return 0


def install_libraries() -> int:
    """Install the libraries of the CODESYS 3.5 project archive that CODESYS 4 does not ship."""
    archive = REPO_ROOT / config.CODESYS4_LIBRARY_ARCHIVE
    shipped = set()
    for path in Path(config.CODESYS4_INSTALL_DIR, "extensions").rglob("*.compiled-library*"):
        shipped.add((path.parent.parent.name.lower(), path.parent.name))
    with tempfile.TemporaryDirectory() as tmp, zipfile.ZipFile(archive) as zf:
        files = []
        for info in zf.infolist():
            if "compiled-library" not in info.filename or "\\" not in info.filename:
                continue
            entry = info.filename.split("\\", 1)[1]
            title = re.match(r"(.+?), (\d+\.\d+\.\d+)(?:\.\d+)? \((.+?)\)\s", entry)
            if not title or (title.group(1).lower(), title.group(2)) in shipped:
                continue
            target = Path(tmp, "%d-%s" % (len(files), entry.split("   ")[-1].strip()))
            target.write_bytes(zf.read(info))
            files.append(str(target))
        print("Installing %d libraries into the CODESYS 4 repository %s" % (len(files), config.CODESYS4_LIBRARY_REPOSITORY))
        return subprocess.call([C4_CLI, "librepo", "install", config.CODESYS4_LIBRARY_REPOSITORY, "--skip-existing", *files])


def build() -> int:
    application = str(APPLICATION)
    # c4-cli can crash on exit after writing Libraries.lock.json: retry when it is killed by a signal
    for _ in range(3):
        status = subprocess.call([C4_CLI, "library", "install", application])
        if status >= 0:
            break
    if status:
        return status
    return subprocess.call([C4_CLI, "bootapp", "compile", application])


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--install-libraries", action="store_true",
                        help="install the libraries CODESYS 4 does not ship from the CODESYS 3.5 project archive")
    parser.add_argument("--build", action="store_true", help="resolve the libraries and compile after generating")
    args = parser.parse_args(argv)
    if args.install_libraries:
        status = install_libraries()
        if status:
            return status
    status = generate()
    if status or not args.build:
        return status
    return build()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

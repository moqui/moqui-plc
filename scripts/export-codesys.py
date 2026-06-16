# encoding:utf-8
from __future__ import print_function

import argparse
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

try:
    text_type = unicode
except NameError:
    text_type = str


print("Saving IEC 61131-3 source files from the project...")


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()

DEFAULT_TARGET_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "st"))
DEFAULT_AX_SCRIPT = os.path.normpath(os.path.join(SCRIPT_DIR, "convert-iec61131-to-ax.py"))
DEFAULT_AX_TARGET_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "simatic-ax"))

TEXTUAL_OUTPUT_EXTENSION = ".st"
GENERATED_SOURCE_SUFFIXES = (
    ".st",
    ".pou",
    ".dut",
    ".gvl",
    ".itf",
    ".pm",
    ".prop",
    ".m",
    ".act",
    ".tl",
    ".gtl",
    ".lib",
    ".task",
    ".tc",
)

IGNORED_SUBTREE_NAMES = set([
    "Library Manager",
    "GlobalTextList",
    "RecipeManager",
])

PLC_LOGIC_NAME = "Plc Logic"
PROJECT_ROOT_NAME = "moqui"
TASK_CONFIGURATION_NAME = "Task Configuration"
TASK_CONFIGURATION_FILE = "configuration.st"
TASK_PROGRAM_HINTS = {
    "StartTask": "MoquiStart",
    "LogDispatcherTask": "LogDispatcher",
    "MqttParameterPubTask": "MqttParameterPub",
    "MqttParameterSubTask": "MqttParameterSub",
    "TestSuiteTask": "TestSuite",
    "PickAndPlaceTestSuiteTask": "PickAndPlaceTestSuite",
}

ATTRIBUTE_LINE_RE = re.compile(r"^\s*\{attribute\s+'[^']+'\}\s*$", re.MULTILINE)

TEXTUAL_CLOSING_KEYWORDS = (
    ("FUNCTION_BLOCK", "END_FUNCTION_BLOCK"),
    ("FUNCTION", "END_FUNCTION"),
    ("PROGRAM", "END_PROGRAM"),
    ("INTERFACE", "END_INTERFACE"),
    ("TYPE", "END_TYPE"),
)

INDENTED_BLOCK_KEYWORDS = (
    "FUNCTION_BLOCK",
    "FUNCTION",
    "PROGRAM",
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Export the CODESYS project directly into a clean IEC 61131-3/ST repository layout."
    )
    parser.add_argument(
        "--target-root",
        default=DEFAULT_TARGET_ROOT,
        help="Destination root for the cleaned IEC 61131-3 export.",
    )
    parser.add_argument(
        "--run-ax-conversion",
        action="store_true",
        help="Run the AX mechanical conversion after the IEC export completes.",
    )
    parser.add_argument(
        "--ax-script",
        default=DEFAULT_AX_SCRIPT,
        help="Path to convert-iec61131-to-ax.py.",
    )
    parser.add_argument(
        "--ax-target-root",
        default=DEFAULT_AX_TARGET_ROOT,
        help="Destination root for the AX tree when --run-ax-conversion is used.",
    )
    parser.add_argument(
        "--ax-python",
        default="python",
        help="Python executable used to run the AX conversion script.",
    )
    parser.add_argument(
        "--keep-target-data",
        action="store_true",
        default=True,
        help="Keep recipe/data directories already present under the target root.",
    )
    parser.add_argument(
        "--no-keep-target-data",
        action="store_false",
        dest="keep_target_data",
        help="Allow cleaning also under data directories in the target root.",
    )
    return parser.parse_args(sys.argv[1:])


def normalize_line_endings(text):
    return text.replace("\r\n", "\n").replace("\r", "\n")


def ensure_text_type(value):
    if value is None:
        return u""
    if isinstance(value, text_type):
        return value
    try:
        return value.decode("utf-8")
    except Exception:
        try:
            return value.decode("latin1")
        except Exception:
            return text_type(value)


def repair_common_mojibake(text):
    markers = (u"â†", u"â€¢", u"â‰", u"â‚¬", u"â€œ", u"â€", u"Ã")
    if not any(marker in text for marker in markers):
        return text
    try:
        repaired = text.encode("latin1").decode("utf-8")
        if repaired:
            return repaired
    except Exception:
        pass
    return text


def normalize_unicode_symbols(text):
    replacements = {
        u"\u2018": "'",
        u"\u2019": "'",
        u"\u201c": '"',
        u"\u201d": '"',
        u"\u2013": "-",
        u"\u2014": "-",
        u"\u2022": "-",
        u"\u2192": "->",
        u"\u2194": "<->",
        u"\u2260": "!=",
        u"\u2264": "<=",
        u"\u2265": ">=",
        u"\u2208": "in",
        u"\u2248": "~=",
        u"\u20ac": "EUR",
        u"\u2500": "-",
        u"\u00a0": " ",
    }
    for source_text, target_text in replacements.items():
        text = text.replace(source_text, target_text)
    return text


def sanitize_export_text(text):
    text = ensure_text_type(text)
    text = repair_common_mojibake(text)
    text = normalize_unicode_symbols(text)
    return text


def trim_blank_edges(text):
    lines = normalize_line_endings(text).split("\n")
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


def strip_codesys_attributes(text):
    if not text:
        return ""
    text = sanitize_export_text(text)
    filtered_lines = []
    for line in normalize_line_endings(text).split("\n"):
        if ATTRIBUTE_LINE_RE.match(line):
            continue
        filtered_lines.append(line)
    return "\n".join(filtered_lines)


def strip_leading_comments_and_whitespace(text):
    working = text.lstrip()
    while working.startswith("(*"):
        closing_index = working.find("*)")
        if closing_index < 0:
            break
        working = working[closing_index + 2 :].lstrip()
    return working


def detect_textual_closing_keyword(declaration):
    header = strip_leading_comments_and_whitespace(declaration)
    upper_header = header.upper()
    for opening_keyword, closing_keyword in TEXTUAL_CLOSING_KEYWORDS:
        if upper_header.startswith(opening_keyword + " ") or upper_header.startswith(opening_keyword + "\n"):
            return closing_keyword
    return ""


def detect_opening_keyword(declaration):
    header = strip_leading_comments_and_whitespace(declaration)
    upper_header = header.upper()
    for opening_keyword, _closing_keyword in TEXTUAL_CLOSING_KEYWORDS:
        if upper_header.startswith(opening_keyword + " ") or upper_header.startswith(opening_keyword + "\n"):
            return opening_keyword
    return ""


def ensure_textual_closure(declaration, implementation):
    closing_keyword = detect_textual_closing_keyword(declaration)
    if not closing_keyword:
        return implementation

    declaration_upper = declaration.upper()
    implementation_upper = implementation.upper()
    if declaration_upper.rstrip().endswith(closing_keyword) or implementation_upper.rstrip().endswith(closing_keyword):
        return implementation

    implementation = implementation.rstrip()
    if implementation:
        return implementation + "\n" + closing_keyword
    return closing_keyword


def indent_nonempty_line(line):
    if not line.strip():
        return line
    return "\t" + line


def indent_textual_block(declaration, implementation):
    opening_keyword = detect_opening_keyword(declaration)
    if opening_keyword not in INDENTED_BLOCK_KEYWORDS:
        return declaration, implementation

    declaration_lines = declaration.split("\n")
    implementation_lines = implementation.split("\n") if implementation else []
    header_seen = False
    formatted_declaration_lines = []

    for line in declaration_lines:
        if not header_seen:
            formatted_declaration_lines.append(line)
            if line.strip().upper().startswith(opening_keyword):
                header_seen = True
            continue
        formatted_declaration_lines.append(indent_nonempty_line(line))

    formatted_implementation_lines = [indent_nonempty_line(line) for line in implementation_lines]
    return "\n".join(formatted_declaration_lines), "\n".join(formatted_implementation_lines)


def compose_textual_object(treeobj):
    sections = []
    if treeobj.has_textual_declaration:
        declaration = trim_blank_edges(strip_codesys_attributes(treeobj.textual_declaration.text))
    else:
        declaration = ""
    if treeobj.has_textual_implementation:
        implementation = trim_blank_edges(strip_codesys_attributes(treeobj.textual_implementation.text))
        implementation = ensure_textual_closure(declaration, implementation)
    elif declaration:
        trailing_closure = ensure_textual_closure(declaration, "")
        if trailing_closure and trailing_closure != declaration:
            declaration_upper = declaration.upper().rstrip()
            trailing_upper = trailing_closure.upper().rstrip()
            if not declaration_upper.endswith(trailing_upper):
                implementation = trailing_closure
            else:
                implementation = ""
        else:
            implementation = ""
    else:
        implementation = ""

    declaration, implementation = indent_textual_block(declaration, implementation)

    if declaration:
        sections.append(declaration)
    if implementation:
        sections.append(implementation)
    if not sections:
        return ""
    return sanitize_export_text("\n\n".join(sections) + "\n")


def is_folder_object(treeobj):
    try:
        return treeobj.is_folder
    except Exception:
        return False


def path_contains(parts, name):
    for part in parts:
        if part == name:
            return True
    return False


def split_relevant_path(raw_parts):
    if PLC_LOGIC_NAME not in raw_parts:
        return None
    plc_logic_index = raw_parts.index(PLC_LOGIC_NAME)
    if len(raw_parts) <= plc_logic_index + 1:
        return None
    if raw_parts[plc_logic_index + 1] != PROJECT_ROOT_NAME:
        return None
    return raw_parts[plc_logic_index + 1 :]


def ensure_dir(path):
    if path and not os.path.exists(path):
        os.makedirs(path)


def remove_empty_dirs(root_path):
    for current_root, dirnames, filenames in os.walk(root_path, topdown=False):
        if dirnames or filenames:
            continue
        if os.path.abspath(current_root) == os.path.abspath(root_path):
            continue
        os.rmdir(current_root)


def clean_target_tree(target_root, keep_target_data):
    ensure_dir(target_root)
    moqui_root = os.path.join(target_root, PROJECT_ROOT_NAME)
    if not os.path.exists(moqui_root):
        return

    for current_root, dirnames, filenames in os.walk(moqui_root):
        relative_root = os.path.relpath(current_root, moqui_root)
        relative_parts = [] if relative_root == "." else relative_root.split(os.sep)
        if keep_target_data and "data" in relative_parts:
            dirnames[:] = []
            continue

        for filename in filenames:
            suffix = os.path.splitext(filename)[1].lower()
            if suffix in GENERATED_SOURCE_SUFFIXES:
                os.remove(os.path.join(current_root, filename))

    remove_empty_dirs(moqui_root)

    plc_configuration_path = os.path.join(target_root, TASK_CONFIGURATION_FILE)
    if os.path.exists(plc_configuration_path):
        os.remove(plc_configuration_path)


def export_task_to_tempfile(treeobj, temp_dir):
    export_path = os.path.join(temp_dir, treeobj.get_name(False) + ".task")
    exports = [treeobj]
    projects.primary.export_native(exports, export_path)
    return export_path


def find_named_child(node, name):
    for child in list(node):
        if child.attrib.get("Name") == name:
            return child
    return None


def read_single_value(node, name, default_value=""):
    if node is None:
        return default_value
    child = find_named_child(node, name)
    if child is None or child.text is None:
        return default_value
    return child.text


def read_time_value(node, name):
    time_node = find_named_child(node, name)
    if time_node is None:
        return ""
    time_value = read_single_value(time_node, "Time", "")
    unit_value = read_single_value(time_node, "Unit", "")
    return normalize_time_literal(time_value, unit_value)


def normalize_time_literal(time_value, unit_value=""):
    if not time_value:
        return ""
    raw_value = time_value.strip()
    if not raw_value:
        return ""
    upper_value = raw_value.upper()
    if upper_value.startswith("TIME#"):
        return "T#" + raw_value[5:]
    if upper_value.startswith("T#"):
        return "T#" + raw_value[2:]
    if not unit_value:
        return "T#{0}".format(raw_value)
    return "T#{0}{1}".format(raw_value, unit_value.strip())


def read_list_values(node, name):
    values = []
    list_node = find_named_child(node, name)
    if list_node is None:
        return values
    for child in list(list_node):
        if child.text is not None and child.text.strip():
            values.append(child.text.strip())
    return values


def parse_task_export(export_path):
    tree = ET.parse(export_path)
    root = tree.getroot()
    object_node = root.find(".//Single[@Name='Object']")
    meta_node = root.find(".//Single[@Name='MetaObject']")
    path_node = root.find(".//Array[@Name='Path']")

    path_parts = []
    if path_node is not None:
        for child in list(path_node):
            if child.text is not None and child.text.strip():
                path_parts.append(child.text.strip())

    task_info = {
        "name": read_single_value(meta_node, "Name"),
        "kind": read_single_value(object_node, "Kindoftask", "Cyclic"),
        "priority": read_single_value(object_node, "Priority", "1"),
        "interval": read_time_value(object_node, "Interval"),
        "event": read_single_value(object_node, "Event", ""),
        "external_event": read_single_value(object_node, "ExternalEvent", ""),
        "task_guid": read_single_value(object_node, "TaskGuid", ""),
        "allow_empty": read_single_value(object_node, "AllowEmpty", "False"),
        "core": read_single_value(object_node, "Core", ""),
        "core2": read_single_value(object_node, "Core2", ""),
        "task_group": read_single_value(object_node, "TaskGroup", ""),
        "time_slice": read_single_value(object_node, "WithinSPSTimeSlicing", ""),
        "pou_list": read_list_values(object_node, "PouList"),
        "path_parts": path_parts,
        "watchdog_enabled": "",
        "watchdog_time": "",
        "watchdog_sensitivity": "",
    }

    watchdog_node = find_named_child(object_node, "Watchdog")
    if watchdog_node is not None:
        task_info["watchdog_enabled"] = read_single_value(watchdog_node, "Enabled", "")
        task_info["watchdog_time"] = read_time_value(watchdog_node, "Time")
        task_info["watchdog_sensitivity"] = read_single_value(watchdog_node, "Sensitivity", "")

    return task_info


def build_task_lines(task_infos, available_programs):
    runtime_tasks = []
    test_tasks = []

    for task_info in task_infos:
        lower_path = [part.lower() for part in task_info["path_parts"]]
        if "test" in lower_path:
            test_tasks.append(task_info)
        else:
            runtime_tasks.append(task_info)

    lines = []
    lines.append("(* Generated from CODESYS task configuration. *)")
    lines.append("")
    lines.append("CONFIGURATION Plc")
    lines.append("   RESOURCE moqui ON PLC")
    lines.append("")

    if runtime_tasks:
        lines.append("      (* Runtime tasks *)")
        lines.extend(render_task_group(runtime_tasks, available_programs))
        lines.append("")

    if test_tasks:
        lines.append("      (* Test tasks *)")
        lines.extend(render_task_group(test_tasks, available_programs))
        lines.append("")

    lines.append("   END_RESOURCE")
    lines.append("END_CONFIGURATION")
    lines.append("")
    return sanitize_export_text("\n".join(lines))


def infer_task_programs(task_info, available_programs):
    if task_info["pou_list"]:
        return task_info["pou_list"]

    task_name = task_info["name"]
    candidates = []
    if task_name in TASK_PROGRAM_HINTS:
        candidates.append(TASK_PROGRAM_HINTS[task_name])
    if task_name.endswith("Task"):
        candidates.append(task_name[:-4])

    resolved = []
    for candidate in candidates:
        if candidate in available_programs and candidate not in resolved:
            resolved.append(candidate)
    return resolved


def render_task_group(tasks, available_programs):
    lines = []
    used_instance_names = {}

    for task_info in tasks:
        kind = (task_info["kind"] or "Cyclic").strip()
        interval = task_info["interval"] or "T#10ms"
        priority = task_info["priority"] or "1"

        lines.append(
            "      (* Kind: {0}; SourcePath: {1} *)".format(
                kind,
                " / ".join(task_info["path_parts"]) if task_info["path_parts"] else "",
            )
        )

        if task_info["watchdog_enabled"]:
            lines.append(
                "      (* WatchdogEnabled: {0}; WatchdogTime: {1}; Sensitivity: {2} *)".format(
                    task_info["watchdog_enabled"],
                    task_info["watchdog_time"] or "n/a",
                    task_info["watchdog_sensitivity"] or "n/a",
                )
            )

        if kind.lower() == "cyclic":
            lines.append(
                "      TASK {0}(INTERVAL := {1}, PRIORITY := {2});".format(
                    task_info["name"], interval, priority
                )
            )
        elif kind.lower() == "freewheeling":
            lines.append("      (* AX_TODO: original task kind is Freewheeling; represented with its exported interval. *)")
            lines.append(
                "      TASK {0}(INTERVAL := {1}, PRIORITY := {2});".format(
                    task_info["name"], interval, priority
                )
            )
        else:
            lines.append(
                "      (* AX_TODO: task kind '{0}' requires manual IEC mapping. *)".format(kind)
            )
            lines.append(
                "      TASK {0}(INTERVAL := {1}, PRIORITY := {2});".format(
                    task_info["name"], interval, priority
                )
            )

        resolved_programs = infer_task_programs(task_info, available_programs)
        for pou_name in resolved_programs:
            instance_name = build_program_instance_name(pou_name, used_instance_names)
            lines.append(
                "      PROGRAM {0} WITH {1} : {2};".format(
                    instance_name,
                    task_info["name"],
                    pou_name,
                )
            )

        lines.append("")

    return lines


def build_program_instance_name(pou_name, used_instance_names):
    base_name = "{0}Instance".format(pou_name)
    next_index = used_instance_names.get(base_name, 0)
    used_instance_names[base_name] = next_index + 1
    if next_index == 0:
        return base_name
    return "{0}{1}".format(base_name, next_index + 1)


class ExportState(object):
    def __init__(self, args):
        self.args = args
        self.target_root = os.path.normpath(args.target_root)
        self.moqui_root = os.path.join(self.target_root, PROJECT_ROOT_NAME)
        self.temp_dir = tempfile.mkdtemp(prefix="moqui_codesys_export_")
        self.task_infos = []
        self.exported_files = 0
        self.created_dirs = set()
        self.available_programs = set()

    def close(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def should_ignore_subtree(self, relevant_parts):
        if not relevant_parts:
            return False
        tail_name = relevant_parts[-1]
        return tail_name in IGNORED_SUBTREE_NAMES

    def ensure_parent_dir(self, target_path):
        parent_dir = os.path.dirname(target_path)
        if parent_dir and parent_dir not in self.created_dirs:
            ensure_dir(parent_dir)
            self.created_dirs.add(parent_dir)

    def save_textual_object(self, relevant_parts, text):
        target_relative_dir = os.path.join(*relevant_parts[:-1]) if len(relevant_parts) > 1 else ""
        target_dir = os.path.join(self.target_root, target_relative_dir)
        target_path = os.path.join(target_dir, relevant_parts[-1] + TEXTUAL_OUTPUT_EXTENSION)
        self.ensure_parent_dir(target_path)
        text = sanitize_export_text(text)
        with io.open(target_path, "w", encoding="utf-8", newline="\n") as output_file:
            output_file.write(text)
        self.exported_files += 1
        if detect_opening_keyword(text) == "PROGRAM":
            self.available_programs.add(relevant_parts[-1])

    def collect_task(self, treeobj):
        export_path = export_task_to_tempfile(treeobj, self.temp_dir)
        self.task_infos.append(parse_task_export(export_path))

    def write_plc_configuration(self):
        if not self.task_infos:
            return
        plc_configuration_path = os.path.join(self.target_root, TASK_CONFIGURATION_FILE)
        plc_configuration_text = sanitize_export_text(build_task_lines(self.task_infos, self.available_programs))
        with io.open(plc_configuration_path, "w", encoding="utf-8", newline="\n") as output_file:
            output_file.write(plc_configuration_text)

    def run_ax_conversion(self):
        ax_script = os.path.normpath(self.args.ax_script)
        if not os.path.exists(ax_script):
            print("AX conversion skipped: script not found at {0}".format(ax_script))
            return

        command = [
            self.args.ax_python,
            ax_script,
            "--source-root",
            self.target_root,
            "--target-root",
            os.path.normpath(self.args.ax_target_root),
        ]
        print("Running AX conversion: {0}".format(" ".join(command)))
        return_code = subprocess.call(command)
        if return_code != 0:
            raise RuntimeError("AX conversion failed with exit code {0}".format(return_code))


def export_tree(treeobj, raw_parts, state):
    name = treeobj.get_name(False)
    current_raw_parts = raw_parts + [name]

    if name == TASK_CONFIGURATION_NAME:
        for child in treeobj.get_children(False):
            export_tree(child, current_raw_parts, state)
        return

    if treeobj.is_task:
        state.collect_task(treeobj)
        return

    relevant_parts = split_relevant_path(current_raw_parts)
    if relevant_parts is None:
        for child in treeobj.get_children(False):
            export_tree(child, current_raw_parts, state)
        return

    if state.should_ignore_subtree(relevant_parts):
        return

    if is_folder_object(treeobj):
        ensure_dir(os.path.join(state.target_root, os.path.join(*relevant_parts)))

    text = compose_textual_object(treeobj)
    if text:
        state.save_textual_object(relevant_parts, text)

    for child in treeobj.get_children(False):
        export_tree(child, current_raw_parts, state)


def main():
    args = parse_args()
    clean_target_tree(os.path.normpath(args.target_root), args.keep_target_data)

    state = ExportState(args)
    try:
        for obj in projects.primary.get_children():
            export_tree(obj, [], state)
        state.write_plc_configuration()
        if args.run_ax_conversion:
            state.run_ax_conversion()
    finally:
        state.close()

    print("Export completed. Generated {0} textual IEC/ST files.".format(state.exported_files))
    try:
        system.ui.info("Export completed successfully.")
    except Exception:
        pass


if __name__ == "__main__":
    main()

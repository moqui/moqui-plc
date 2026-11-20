from __future__ import annotations

import importlib.util
import json
import re
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import moqui_plc_config as config  # noqa: E402

_spec = importlib.util.spec_from_file_location("codesys4", SCRIPTS / "convert-iec61131-to-codesys4.py")
c4 = importlib.util.module_from_spec(_spec)
sys.modules["codesys4"] = c4
_spec.loader.exec_module(c4)


class Codesys4PortTests(unittest.TestCase):
    def test_global_variables_are_qualified(self) -> None:
        owners = {"init": "ec", "max": "MoquiConf", "workeffort": "ec"}
        text = (
            "VAR\n\tlocal : ARRAY[1..max] OF INT;\n\tw : WorkEffort;\nEND_VAR\n"
            "IF init THEN f(init := init); a.init := 1; END_IF\n"
        )
        result = c4.qualify_globals(text, owners, set(), types={"workeffort"})
        self.assertIn("ARRAY[1..MoquiConf.max]", result)
        self.assertIn("w : WorkEffort;", result)
        self.assertIn("IF ec.init THEN f(init := ec.init); a.init := 1;", result)

    def test_local_declaration_hides_global(self) -> None:
        result = c4.qualify_globals("x := init;", {"init": "ec"}, {"init"})
        self.assertEqual("x := init;", result)

    def test_drop_declarations_removes_comment_above(self) -> None:
        text = "VAR\n\t(* adapter *)\n\tethernet : IoDrvEthernet;\n\n\taxis : AXIS_REF;\nEND_VAR\n"
        self.assertEqual("VAR\n\n\taxis : AXIS_REF;\nEND_VAR\n", c4.drop_declarations(text, "ethernet"))
        text = "VAR\n\tdgs : NetworkDiagnostics;\n\tlogger : LoggerFacade;\nEND_VAR\n"
        self.assertEqual("VAR\n\tlogger : LoggerFacade;\nEND_VAR\n",
                         c4.drop_declarations(text, r"\w+", "NetworkDiagnostics"))

    def test_only_enabled_tasks_are_active(self) -> None:
        text = c4.CONFIGURATION_FILE.read_text(encoding="utf-8")
        output = c4.task_configuration(text)
        active = json.loads(re.sub(r"(?m)^\s*//.*\n", "", output))["taskGroups"][0]["tasks"]
        self.assertEqual(set(config.CODESYS4_ENABLED_TASKS), set(active))
        self.assertIn(config.CODESYS4_BUS_CYCLE_TASK, active)
        self.assertIn('// "StartTask": {', output)
        self.assertEqual(10000, active["AxisGroupTestSuiteTask"]["interval"])

    def test_device_tree_list(self) -> None:
        obj = c4.device_tree()
        self.assertEqual(config.CODESYS4_DEVICE_TREE_LIST, obj.name)
        self.assertEqual("gvl", obj.kind)
        self.assertNotIn("ethernet", obj.declared)
        self.assertIn("j1 : SM3_Basic.AXIS_REF_VIRTUAL_SM3;", obj.text)


if __name__ == "__main__":
    unittest.main()

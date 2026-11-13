from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import moqui_plc_config as config  # noqa: E402
from st_dialect import DialectRewriter, enumeration_types, flatten_nested_comments, global_variable_lists  # noqa: E402


def rewriter(target: str, gvls=(), enums=()) -> DialectRewriter:
    return DialectRewriter(
        target=target,
        namespaces=config.EXTERNAL_LIBRARY_NAMESPACES,
        renamed=config.EXTERNAL_LIBRARY_RENAMED_SYMBOLS,
        parameter_lists=config.EXTERNAL_LIBRARY_PARAMETER_LISTS,
        global_lists=gvls,
        enumerations=enums,
    )


class DialectRewriterTests(unittest.TestCase):
    def test_library_namespaces_are_dropped_and_collisions_renamed(self) -> None:
        source = (
            "client : MQTT.MQTTClient;\n"
            "e : JSON.ERROR := JSON.ERROR.NO_ERROR;\n"
            "p : DED.CAA.PVOID;\n"
            "n : UDINT := MQTT.MQTTParam.g_udiMaxPacketSize;\n"
        )
        text = rewriter("rusty").rewrite(source)
        self.assertEqual(
            "client : MQTTClient;\ne : JSON_ERROR := JSON_ERROR.NO_ERROR;\np : PVOID;\nn : UDINT := g_udiMaxPacketSize;\n",
            text,
        )

    def test_comments_and_strings_are_untouched(self) -> None:
        source = "(* MQTT.MQTTClient *) s := 'JSON.ERROR'; x := MQTT.MQTT_QOS.QoS0;\n"
        text = rewriter("rusty").rewrite(source)
        self.assertEqual("(* MQTT.MQTTClient *) s := 'JSON.ERROR'; x := MQTT_QOS.QoS0;\n", text)

    def test_global_variable_list_qualifier_is_dropped(self) -> None:
        text = rewriter("rusty", gvls=["ec"]).rewrite("IF ec.init THEN x := spec.init; END_IF;\n")
        self.assertEqual("IF init THEN x := spec.init; END_IF;\n", text)

    def test_union_becomes_struct(self) -> None:
        text = rewriter("rusty").rewrite("TYPE P : UNION\n\ta : INT;\nEND_UNION END_TYPE\n")
        self.assertEqual("TYPE P : STRUCT\n\ta : INT;\nEND_STRUCT END_TYPE\n", text)

    def test_rusty_reference_check_and_uxint_conversion(self) -> None:
        text = rewriter("rusty").rewrite("IF __ISVALIDREF(master) THEN n := __UXINT_TO_INT(c); END_IF;\n")
        self.assertEqual("IF (ADR(master) <> 0) THEN n := TO_INT(c); END_IF;\n", text)
        self.assertIn("__ISVALIDREF", rewriter("ironplc").rewrite("b := __ISVALIDREF(master);\n"))

    def test_atomic_add_is_written_as_declared_function(self) -> None:
        for target in ("rusty", "ironplc"):
            text = rewriter(target).rewrite("n := __XADD(ADR(count), 1); (* __XADD(x) *)\n")
            self.assertIn("n := MOQUI_XADD(ADR(count), 1);", text)
            self.assertIn("(* __XADD(x) *)", text)

    def test_ironplc_drops_enum_qualifiers_and_flattens_comments(self) -> None:
        source = "(* a (* b *) c *)\nIF s = MainStatus.Idle THEN m := MC_BUFFER_MODE.aborting; END_IF;\n"
        text = rewriter("ironplc", enums=["MainStatus", "MC_BUFFER_MODE"]).rewrite(source)
        self.assertEqual("(* a [ b ] c *)\nIF s = Idle THEN m := aborting; END_IF;\n", text)
        self.assertIn("MainStatus.Idle", rewriter("rusty", enums=["MainStatus"]).rewrite(source))

    def test_ironplc_moves_tasks_before_programs(self) -> None:
        source = "CONFIGURATION c\nRESOURCE r ON PLC\nPROGRAM p WITH t : Main;\nTASK t(INTERVAL := T#10ms);\nEND_RESOURCE\nEND_CONFIGURATION\n"
        text = rewriter("ironplc").rewrite(source)
        self.assertLess(text.index("TASK t"), text.index("PROGRAM p"))

    def test_flatten_keeps_strings(self) -> None:
        self.assertEqual("s := '(* x *)';\n", flatten_nested_comments("s := '(* x *)';\n"))


class TreeDiscoveryTests(unittest.TestCase):
    def test_global_lists_and_enumerations_are_found(self) -> None:
        texts = {
            Path("ec.st"): "(* context *)\nVAR_GLOBAL\n\tinit : BOOL;\nEND_VAR\n",
            Path("Main.st"): "PROGRAM Main\nVAR_GLOBAL x : INT; END_VAR\nEND_PROGRAM\n",
        }
        self.assertEqual(["ec"], global_variable_lists(texts))
        self.assertEqual(["Mode"], enumeration_types(["TYPE Mode : (A, B); END_TYPE\n(* TYPE Fake : (X) *)\n"]))

    def test_interface_declarations_cover_every_external_namespace(self) -> None:
        interfaces = Path(config.RUST_PLC_INTERFACES_ROOT)
        names = {p.parent.name for p in interfaces.rglob("*.st")}
        self.assertEqual(
            {"plcopen-motion", "codesys-softmotion", "codesys-iiot", "codesys-system", "codesys-util", "device-tree"},
            names,
        )


if __name__ == "__main__":
    unittest.main()

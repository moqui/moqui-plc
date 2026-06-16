from __future__ import annotations

import unittest
from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from ax_port.compatibility import apply_file_compatibility
from ax_port.transforms import convert_text


class ConservativeTransformTests(unittest.TestCase):
    def test_preserves_comments_and_indentation(self) -> None:
        source = (
            "FUNCTION_BLOCK Example\n"
            "\tVAR_INPUT\n"
            "\t\taxis : REFERENCE TO AxisType; (* keep exactly *)\n"
            "\tEND_VAR\n"
            "\tIF enabled THEN\n"
            "\t\tstate := State.Ready;\n"
            "\tEND_IF\n"
            "END_FUNCTION_BLOCK\n"
        )
        result = convert_text(Path("Example.st"), source, {"State"})
        self.assertIn("\t\taxis : REF_TO AxisType; (* keep exactly *)", result.text)
        self.assertIn("\t\tstate := State#Ready;", result.text)
        self.assertIn("\tEND_IF;", result.text)
        self.assertIn("(* keep exactly *)", result.text)

    def test_ref_assignment_keeps_leading_whitespace(self) -> None:
        source = "\tmaster REF= axis;\n"
        result = convert_text(Path("Example.st"), source, set())
        self.assertEqual("\tmaster := REF(axis);\n", result.text)

    def test_compatibility_is_separate_from_syntax(self) -> None:
        source = "\tref : REAL;\n\tref := value;\n"
        syntax = convert_text(Path("Actuator.st"), source, set())
        self.assertEqual(source, syntax.text)
        compatibility = apply_file_compatibility(Path("Actuator.st"), syntax.text)
        self.assertIn("referenceValue : REAL;", compatibility.text)
        self.assertIn("referenceValue := value;", compatibility.text)


if __name__ == "__main__":
    unittest.main()

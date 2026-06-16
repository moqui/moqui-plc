from pathlib import Path
import shutil
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from ax_port.policy import (
    POLICIES,
    PROCESS_MANUAL_OVERRIDE_STEMS,
    MOTION_MANUAL_OVERRIDE_STEMS,
)


class MotionPolicyTests(unittest.TestCase):
    def test_motion_types_are_included(self):
        policy = POLICIES["motion"]
        self.assertTrue(policy.includes(Path("framework/src/main/org/moqui/motion/AxisCmd.st")))
        self.assertTrue(policy.includes(Path("framework/src/main/org/moqui/motion/AxisGroupStatus.st")))

    def test_motion_function_blocks_are_manual(self):
        policy = POLICIES["motion"]
        self.assertFalse(policy.includes(Path("framework/src/main/org/moqui/motion/Axis.st")))
        self.assertFalse(policy.includes(Path("framework/src/main/org/moqui/motion/AxisGroup.st")))

    def test_motion_examples_and_tests_are_excluded(self):
        policy = POLICIES["motion"]
        self.assertFalse(policy.includes(Path("framework/src/test/axis/AxisTestSuite.st")))
        self.assertFalse(policy.includes(Path("framework/src/test/pnp/PickAndPlaceTestSuite.st")))
        self.assertFalse(policy.includes(Path("framework/src/test/robot-arm/TestRobotArmPlanning.st")))


class ProcessManualOverrideTests(unittest.TestCase):
    """PROCESS_POLICY must not include Axis or AxisGroup in its override set."""

    def test_axis_override_excluded_from_process(self):
        self.assertNotIn(
            Path("framework/src/main/org/moqui/motion/Axis"),
            PROCESS_MANUAL_OVERRIDE_STEMS,
        )

    def test_axis_group_override_excluded_from_process(self):
        self.assertNotIn(
            Path("framework/src/main/org/moqui/motion/AxisGroup"),
            PROCESS_MANUAL_OVERRIDE_STEMS,
        )

    def test_process_policy_manual_override_stems_match(self):
        self.assertEqual(POLICIES["process"].manual_override_stems, PROCESS_MANUAL_OVERRIDE_STEMS)

    def test_motion_duts_not_staged_by_process(self):
        policy = POLICIES["process"]
        duts = [
            "AxisCmd.st",
            "AxisStatus.st",
            "AxisInternalStatus.st",
            "AxisGroupCmd.st",
            "AxisGroupStatus.st",
            "AxisGroupInternalStatus.st",
        ]
        for dut in duts:
            path = Path(f"framework/src/main/org/moqui/motion/{dut}")
            self.assertFalse(
                policy.includes(path),
                msg=f"Process profile must not include {dut}",
            )


class MotionManualOverrideTests(unittest.TestCase):
    """MOTION_POLICY must include Axis and AxisGroup in its override set."""

    def test_axis_override_included_in_motion(self):
        self.assertIn(
            Path("framework/src/main/org/moqui/motion/Axis"),
            MOTION_MANUAL_OVERRIDE_STEMS,
        )

    def test_axis_group_override_included_in_motion(self):
        self.assertIn(
            Path("framework/src/main/org/moqui/motion/AxisGroup"),
            MOTION_MANUAL_OVERRIDE_STEMS,
        )

    def test_motion_policy_manual_override_stems_match(self):
        self.assertEqual(POLICIES["motion"].manual_override_stems, MOTION_MANUAL_OVERRIDE_STEMS)

    def test_six_motion_duts_staged_by_motion(self):
        policy = POLICIES["motion"]
        duts = [
            "AxisCmd.st",
            "AxisStatus.st",
            "AxisInternalStatus.st",
            "AxisGroupCmd.st",
            "AxisGroupStatus.st",
            "AxisGroupInternalStatus.st",
        ]
        for dut in duts:
            path = Path(f"framework/src/main/org/moqui/motion/{dut}")
            self.assertTrue(
                policy.includes(path),
                msg=f"Motion profile must include {dut}",
            )


class StagingSimulationTests(unittest.TestCase):
    """Simulate staging to verify Axis/AxisGroup placement per profile.

    Uses temporary directories; does not touch the real source tree.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        # Create fake Axis.st and AxisGroup.st in a fake target tree
        motion_dir = self.tmp / "target" / "framework" / "src" / "main" / "org" / "moqui" / "motion"
        motion_dir.mkdir(parents=True)
        (motion_dir / "Axis.st").write_text("FUNCTION_BLOCK Axis END_FUNCTION_BLOCK\n", encoding="utf-8")
        (motion_dir / "AxisGroup.st").write_text("FUNCTION_BLOCK AxisGroup END_FUNCTION_BLOCK\n", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _axis_path(self) -> Path:
        return Path("framework/src/main/org/moqui/motion/Axis")

    def _axis_group_path(self) -> Path:
        return Path("framework/src/main/org/moqui/motion/AxisGroup")

    def test_process_staging_excludes_axis(self):
        stems = POLICIES["process"].manual_override_stems
        self.assertNotIn(self._axis_path(), stems)

    def test_process_staging_excludes_axis_group(self):
        stems = POLICIES["process"].manual_override_stems
        self.assertNotIn(self._axis_group_path(), stems)

    def test_motion_staging_preserves_axis(self):
        stems = POLICIES["motion"].manual_override_stems
        self.assertIn(self._axis_path(), stems)

    def test_motion_staging_preserves_axis_group(self):
        stems = POLICIES["motion"].manual_override_stems
        self.assertIn(self._axis_group_path(), stems)

    def test_process_does_not_restore_axis_from_target(self):
        """Policy contract: Axis/AxisGroup stems absent from process, present in motion."""
        process_stems = POLICIES["process"].manual_override_stems
        motion_stems = POLICIES["motion"].manual_override_stems
        for stem in (self._axis_path(), self._axis_group_path()):
            self.assertNotIn(stem, process_stems,
                             msg=f"{stem.name} must not be restored by process staging")
            self.assertIn(stem, motion_stems,
                          msg=f"{stem.name} must be preserved by motion staging")


if __name__ == "__main__":
    unittest.main()

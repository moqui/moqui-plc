(* Device tree objects that CODESYS generates from the project's device
 * configuration and that moqui-plc code references by name: the Ethernet
 * adapter, the SoftMotion drives, kinematic groups and cam tables used by the
 * test suites.
 *
 * Declarations only. A runtime that hosts moqui-plc creates these objects from
 * its own I/O configuration (for example an EtherCAT master and its drives).
 *)

VAR_GLOBAL
    (* fieldbus adapter, NetworkDiagnostics *)
    ethernet : IoDrvEthernet;

    (* AxisTestSuite *)
    MasterDrive : AXIS_REF;
    SlaveDrive : AXIS_REF;
    TestCam : MC_CAM_REF;

    (* AxisGroupTestSuite: six-joint arm *)
    TestRobotArm : AXES_GROUP_REF;
    j1 : AXIS_REF;
    j2 : AXIS_REF;
    j3 : AXIS_REF;
    j4 : AXIS_REF;
    j5 : AXIS_REF;
    j6 : AXIS_REF;

    (* PickAndPlaceTestSuite: tripod robot, rotary table, conveyor belt *)
    Tripod : AXES_GROUP_REF;
    Tripod1 : AXIS_REF;
    Tripod2 : AXIS_REF;
    Tripod3 : AXIS_REF;
    DriveRotaryTable : AXIS_REF;
    DriveConveyorBelt : AXIS_REF;
END_VAR

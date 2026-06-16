(* Generated from CODESYS task configuration. *)

CONFIGURATION Plc
   RESOURCE moqui ON PLC

      (* Runtime tasks *)
      (* Kind: Cyclic; SourcePath: Plc / PLC Logic / moqui / Task Configuration *)
      (* WatchdogEnabled: False; WatchdogTime: T#3ms; Sensitivity: 1 *)
      TASK StartTask(INTERVAL := T#10ms, PRIORITY := 1);
      PROGRAM MoquiStartInstance WITH StartTask : MoquiStart;

      (* Kind: Cyclic; SourcePath: Plc / PLC Logic / moqui / Task Configuration *)
      (* WatchdogEnabled: False; WatchdogTime: n/a; Sensitivity: 1 *)
      TASK LogDispatcherTask(INTERVAL := T#1000ms, PRIORITY := 3);
      PROGRAM LogDispatcherInstance WITH LogDispatcherTask : LogDispatcher;

      (* Kind: Cyclic; SourcePath: Plc / PLC Logic / moqui / Task Configuration *)
      (* WatchdogEnabled: False; WatchdogTime: n/a; Sensitivity: 1 *)
      TASK MqttParameterPubTask(INTERVAL := T#3000ms, PRIORITY := 3);
      PROGRAM MqttParameterPubInstance WITH MqttParameterPubTask : MqttParameterPub;

      (* Kind: Cyclic; SourcePath: Plc / PLC Logic / moqui / Task Configuration *)
      (* WatchdogEnabled: False; WatchdogTime: n/a; Sensitivity: 1 *)
      TASK MqttParameterSubTask(INTERVAL := T#1000ms, PRIORITY := 1);
      PROGRAM MqttParameterSubInstance WITH MqttParameterSubTask : MqttParameterSub;


      (* Test tasks *)
      (* Kind: Cyclic; SourcePath: Plc / PLC Logic / moqui / Task Configuration / test *)
      (* WatchdogEnabled: False; WatchdogTime: n/a; Sensitivity: 1 *)
      TASK AxisTestSuiteTask(INTERVAL := T#10ms, PRIORITY := 1);
      PROGRAM AxisTestSuiteInstance WITH AxisTestSuiteTask : AxisTestSuite;

      (* Kind: Cyclic; SourcePath: Plc / PLC Logic / moqui / Task Configuration / test *)
      (* WatchdogEnabled: False; WatchdogTime: n/a; Sensitivity: 1 *)
      TASK TestSuiteTask(INTERVAL := T#10ms, PRIORITY := 1);
      PROGRAM TestSuiteInstance WITH TestSuiteTask : TestSuite;

      (* Kind: Cyclic; SourcePath: Plc / PLC Logic / moqui / Task Configuration / test *)
      (* WatchdogEnabled: False; WatchdogTime: n/a; Sensitivity: 1 *)
      TASK DeviceTestSuiteTask(INTERVAL := T#10ms, PRIORITY := 1);
      PROGRAM DeviceTestSuiteInstance WITH DeviceTestSuiteTask : DeviceTestSuite;

      (* Kind: Cyclic; SourcePath: Plc / PLC Logic / moqui / Task Configuration / test *)
      (* WatchdogEnabled: False; WatchdogTime: n/a; Sensitivity: n/a *)
      TASK TestRobotArmPlanningTask(INTERVAL := T#20ms, PRIORITY := 11);
      PROGRAM TestRobotArmPlanningInstance WITH TestRobotArmPlanningTask : TestRobotArmPlanning;

      (* Kind: Cyclic; SourcePath: Plc / PLC Logic / moqui / Task Configuration / test *)
      (* WatchdogEnabled: False; WatchdogTime: n/a; Sensitivity: 1 *)
      TASK AxisGroupTestSuiteTask(INTERVAL := T#10ms, PRIORITY := 1);
      PROGRAM AxisGroupTestSuiteInstance WITH AxisGroupTestSuiteTask : AxisGroupTestSuite;

      (* Kind: Cyclic; SourcePath: Plc / PLC Logic / moqui / Task Configuration / test *)
      (* WatchdogEnabled: False; WatchdogTime: n/a; Sensitivity: 1 *)
      TASK ActuatorGroupTestSuiteTask(INTERVAL := T#10ms, PRIORITY := 1);
      PROGRAM ActuatorGroupTestSuiteInstance WITH ActuatorGroupTestSuiteTask : ActuatorGroupTestSuite;

      (* Kind: Freewheeling; SourcePath: Plc / PLC Logic / moqui / Task Configuration / test *)
      (* WatchdogEnabled: False; WatchdogTime: n/a; Sensitivity: 1 *)
      (* AX_TODO: original task kind is Freewheeling; represented with its exported interval. *)
      TASK TestTripodPlanningTask(INTERVAL := T#20ms, PRIORITY := 11);
      PROGRAM TestTripodPlanningInstance WITH TestTripodPlanningTask : TestTripodPlanning;

      (* Kind: Cyclic; SourcePath: Plc / PLC Logic / moqui / Task Configuration / test *)
      (* WatchdogEnabled: False; WatchdogTime: n/a; Sensitivity: 1 *)
      TASK PickAndPlaceTestSuiteTask(INTERVAL := T#10ms, PRIORITY := 1);
      PROGRAM PickAndPlaceTestSuiteInstance WITH PickAndPlaceTestSuiteTask : PickAndPlaceTestSuite;


   END_RESOURCE
END_CONFIGURATION

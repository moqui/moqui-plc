# Moqui Framework for PLC

Moqui Framework for PLC is an IEC 61131-3 framework for building machine and process applications around reusable motion, device, logging, diagnostics, and MQTT components.

The core motion abstractions are:
- `Axis`: a single-axis wrapper around PLCopen Motion Control Part 1/2 function blocks for servo drives and motors.
- `AxisGroup`: a coordinated multi-axis wrapper around PLCopen Motion Control Part 4 for robot and kinematic groups.
- `Actuator`: a bistable device controller with handshake-based enable/disable sequencing and diagnostics.
- `ActuatorGroup`: a demand-driven group controller for multiple bistable actuators, with staging, anti-cycling delays, and wear-balancing rotation.

Typical robot use cases include conveyors with cutters, pick-and-place cells, tripod/robot-arm kinematics, and coordinated axis groups driven through a common FSM-oriented application layer.

The repository also contains `mantle-hvac`, an application example showing how the framework can be used outside robotics to orchestrate HVAC equipment, device rules, and supervisory state machines on top of the same reusable PLC components.

Main source areas:
- `iec61131/moqui/framework/src/main`: reusable framework POUs, DUTs, GVLs, and utilities.
- `iec61131/moqui/framework/src/test`: motion, device, and pick-and-place test suites.
- `iec61131/moqui/runtime/component/mantle-hvac`: example runtime component built on the framework.

The IEC 61131-3 source exports under `iec61131/moqui` can be imported into any compliant IDE (CODESYS, Siemens AX, etc.). `iec61131.zip` contains the same exports as a ready-to-import archive.

`MoquiStart` is the entry-point orchestrator: it initializes clocks, diagnostics, logging, input/output processing, configuration loading, and then dispatches the application `Main` POU.

### Prerequisites
To open the Codesys project for testing, you need to download the Codesys IDE from the following link:
* [Codesys Store](https://store.codesys.com/en/codesys.html)

### Testing Setup
To be able to carry out automatic tests or start the framework, it is necessary to connect the Codesys tasks to the appropriate PLC PROGRAM.

#### Pick and Place (PnO)
To run the **pick and place (pnp)** test suite, you need to link:
* `TestTripodPlanningTask` --> `TestTripodPlanning`
* `PickAndPlaceTestSuiteTask` --> `PickAndPlaceTestSuite`

#### Robot Arm 6 DOF
To run the **robot arm with 6 DOF** test suite, you need to link:
* `TestRobotArmPlanningTask` --> `TestRobotArmPlanning`
* `AxisGroupTestSuiteTask` --> `AxisGroupTestSuite`

(* Hardware-abstraction layer for the conveyance environment.
 *
 * Responsibilities:
 *   1. Drive the rotary-table and conveyor-belt axes with MC_Power + MC_MoveVelocity.
 *      (continuous rotation/feed - no homing required for these drives).
 *   2. Run the cone state machines (three cones on the conveyor belt).
 *   3. Run the ring state machines (two rings on the rotary table).
 *   4. Publish activeCone and ringOnTable each scan.
 *)
FUNCTION_BLOCK Environment
	
	VAR_INPUT
		operationType : OperatingMode;
	END_VAR
	VAR
		(* Drive axes - MC_Power + MC_MoveVelocity, no homing for continuous drives *)
		powRotaryTable : SM3_Basic.MC_Power := (Enable := TRUE, bRegulatorOn := TRUE, bDriveStart := TRUE);
		powConveyorBelt : SM3_Basic.MC_Power := (Enable := TRUE, bRegulatorOn := TRUE, bDriveStart := TRUE);
		mvRotaryTable : SM3_Basic.MC_MoveVelocity := (Execute := TRUE, Velocity := PickAndPlaceConsts.tableVelocity, Acceleration := PickAndPlaceConsts.tableAcceleration, Deceleration := PickAndPlaceConsts.tableAcceleration, Jerk := 1000);
		mvConveyorBelt : SM3_Basic.MC_MoveVelocity := (Execute := TRUE, Velocity := PickAndPlaceConsts.beltVelocity, Acceleration := PickAndPlaceConsts.beltAcceleration, Deceleration := PickAndPlaceConsts.beltAcceleration, Jerk := 1000);

		(* Cones - three instances on the belt (circular chain) *)
		cone1 : Cone;
		cone2 : Cone;
		cone3 : Cone;

		(* Rings - two instances on the rotary table *)
		ring1 : Ring;
		ring2 : Ring;

		ring1StartPos : SM3_Robotics.MC_COORD_REF := (X :=  75, Y := 100, Z := 0);
		ring2StartPos : SM3_Robotics.MC_COORD_REF := (X := -75, Y := 100, Z := 0);

		init : BOOL := TRUE; (* First-scan bootstrap flag *)
	END_VAR

	(* Rotary table and conveyor belt drives - power and continuous velocity *)
	powRotaryTable(Axis := deviceTree.DriveRotaryTable);
	powConveyorBelt(Axis := deviceTree.DriveConveyorBelt);

	(* Drive status diagnostics - updated before the guard so they are visible even if RETURN fires *)
	PickAndPlaceData.pnp.rotaryTableAxisReady := powRotaryTable.Status;
	PickAndPlaceData.pnp.rotaryTableAxisError := powRotaryTable.Error;

	(* Wait for both drives powered before running cones / rings *)
	IF NOT (powRotaryTable.Status AND powConveyorBelt.Status) THEN
		init := TRUE;
		RETURN;
	END_IF;
	mvRotaryTable(Axis := deviceTree.DriveRotaryTable);
	mvConveyorBelt(Axis := deviceTree.DriveConveyorBelt);

	(* Wait for the tripod group to be ready before starting cone/ring FSMs *)
	IF NOT PickAndPlaceData.pnp.readyForMotion THEN
		RETURN;
	END_IF;

	(* Cone state machines *)
	(*
	 * cone1.start := init bootstraps the circular chain on the first scan:
	 *   cone1 activates immediately (skips the chain-guard condition).
	 *   cone2 and cone3 activate in sequence once cone1 advances on the belt.
	 *)
	cone1(activeConePtr := PickAndPlaceData.pnp.activeConePtr, previousConePtr := ADR(cone3), start := init);
	cone2(activeConePtr := PickAndPlaceData.pnp.activeConePtr, previousConePtr := ADR(cone1), start := FALSE);
	cone3(activeConePtr := PickAndPlaceData.pnp.activeConePtr, previousConePtr := ADR(cone2), start := FALSE);

	(* Ring state machines *)
	IF init THEN
		ring1.startPos := ring1StartPos;
		ring2.startPos := ring2StartPos;
	END_IF;

	ring1(otherRingPtr := ADR(ring2));
	ring2(otherRingPtr := ADR(ring1));

	(* Publish environment state to pnp *)
	PickAndPlaceData.pnp.ringOnTable := ring1.onTable OR ring2.onTable;

	(* Ring FSM diagnostics *)
	PickAndPlaceData.pnp.ring1State := ring1.state;
	PickAndPlaceData.pnp.ring1TrtDone := ring1.trt.Done;
	PickAndPlaceData.pnp.ring1TrtError := ring1.trt.Error;

	init := FALSE;
	END_FUNCTION_BLOCK

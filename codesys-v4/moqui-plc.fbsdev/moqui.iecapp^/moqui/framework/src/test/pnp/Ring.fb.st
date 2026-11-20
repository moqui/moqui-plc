(* Rotary-table ring tracking.
 *
 * State machine:
 *   0   Ring at start position - waits for safe conditions + trigger
 *   10  Linking PCS_1 to ring via MC_TrackRotaryTable
 *   20  Ring on table, spinning - waits until robot is free
 *   30  Waiting for robot to pick up ring
 *   40  Ring attached to robot - follows TCP position
 *   50  Ring placed on cone - follows cone position until cone leaves belt
 *)
FUNCTION_BLOCK Ring
	
	VAR_INPUT
		otherRingPtr : POINTER TO Ring; (* The other ring in the pair *)
		startPos : SM3_Robotics.MC_COORD_REF; (* Initial position in MCS *)
	END_VAR
	VAR_OUTPUT
		pos : SM3_Robotics.MC_COORD_REF;
		state  : DINT;
		onTable : BOOL;
	END_VAR
	VAR
		stateOld : DINT;
		frame : SM3_Robotics.SMC_Frame;
		rotaryTableOrigin : SM3_Robotics.MC_COORD_REF :=
			(X := PickAndPlaceConsts.tableTransX, Y := PickAndPlaceConsts.tableTransY, Z := PickAndPlaceConsts.tableTransZ);
		initialObjectPosition : SM3_Robotics.MC_COORD_REF := (Y := 400, Z := 30);
		trt : SM3_Robotics.MC_TrackRotaryTable := (
			RotaryTableOrigin := rotaryTableOrigin,
			initialObjectPosition := initialObjectPosition,
			CoordSystem := SM3_Robotics.SMC_COORD_SYSTEM.PCS_1);
		conePtr : POINTER TO Cone;
	END_VAR

	REPEAT
		stateOld := state;
		CASE state OF

		0 :	(* Ring at start position - wait for safe conditions and cycle trigger *)
			pos := startPos;

			IF PickAndPlaceData.pnp.readyForMotion AND (otherRingPtr^.state = 0 OR otherRingPtr^.state >= 40)
					AND (PickAndPlaceData.pnp.setRing OR PickAndPlaceData.pnp.automaticPnp) THEN
				trt(Execute := FALSE,
				    AxisGroup := deviceTree.Tripod,
				    RotaryTable := deviceTree.DriveRotaryTable);
				trt.Execute := TRUE;
				state := state + 10;
			END_IF;

		10 : (* Linking PCS_1 to the position of this ring *)
			IF trt.Done THEN
				state := state + 10;
			END_IF;

		20 : (* Ring on rotary table, spinning - wait until robot is free to pick *)
			trt.cs.GetPose(cs := frame, fTime := deviceTree.Tripod1.fTaskCycle);
			SM3_Robotics.SMC_Frame_To_CoordRef(c := pos, f := frame);

			IF NOT PickAndPlaceData.pnp.ringAttached THEN
				state := state + 10;
			END_IF;

		30 : (* Waiting for robot to attach to ring *)
			trt.cs.GetPose(cs := frame, fTime := deviceTree.Tripod1.fTaskCycle);
			SM3_Robotics.SMC_Frame_To_CoordRef(c := pos, f := frame);

			IF PickAndPlaceData.pnp.ringAttached THEN
				state := state + 10;
			END_IF;

		40 : (* Ring attached to robot - follow TCP position *)
			pos.X := PickAndPlaceData.pnp.tripodActualPos.c.X;
			pos.Y := PickAndPlaceData.pnp.tripodActualPos.c.Y;
			pos.Z := PickAndPlaceData.pnp.tripodActualPos.c.Z - PickAndPlaceConsts.tcpRing;

			IF NOT PickAndPlaceData.pnp.ringAttached THEN
				conePtr := PickAndPlaceData.pnp.targetConePtr;
				state := state + 10;
			END_IF;

		50 : (* Ring placed on cone - follow cone position until cone exits belt *)
			pos.X := conePtr^.pos.X;
			pos.Y := conePtr^.pos.Y;
			pos.Z := conePtr^.pos.Z;

			IF NOT conePtr^.onBelt THEN
				state := 0;
			END_IF;
		END_CASE;

		trt(AxisGroup := deviceTree.Tripod, RotaryTable := deviceTree.DriveRotaryTable);
	UNTIL state = stateOld END_REPEAT;

	onTable := state = 20 OR state = 30;
	END_FUNCTION_BLOCK

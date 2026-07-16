FUNCTION_BLOCK JsonToParametersMapper
	VAR_EXTERNAL
		dev : DeviceFacade;
	END_VAR
	VAR_INPUT
	    jsonKey : WSTRING(255) := "";
	    jsonValue : JSON.JSONElement;
	END_VAR

	(* Args validation *)
	IF (jsonKey = "") THEN RETURN; END_IF;

	(* Application-specific mapping example (documentation only).
	 * The agent generates the executable mapper from the reviewed
	 * DeviceRequestItem live-parameter whitelist for each Application. *)

	(* --- 6-DOF robot arm trajectory (moqui-device export#Trajectory) ---
	 * JSON payload shape (received on MqttParameterSub topic, e.g. moqui/robot/arm1/trajectory):
	 *   { "approximatedFunctionId": "100051", "waypointCount": 10,
	 *     "axes": { "J1": [θ0,θ1,…,θ9], "J2": […], …, "J6": […] } }
	 *
	 * Each axis key ("J1"…"J6") carries a JSON array of REAL values (radians, sequenceNum order).
	 * The current FB handles only scalar values (jsonValue.value.lrValue).
	 * When implemented, each array branch would iterate jsonValue.elements and populate
	 * the application-specific trajectory buffer, e.g.:
	 *
	 *   ELSIF jsonKey = "J1" THEN
	 *       FOR i := 0 TO MIN(jsonValue.count - 1, MAX_WAYPOINTS - 1) DO
	 *           dev.trajectory.joint[0, i] := TO_LREAL(jsonValue.elements[i].value.lrValue);
	 *       END_FOR;
	 *   ELSIF jsonKey = "J2" THEN ...
	 *   (* J3→joint[2,i], J4→joint[3,i], J5→joint[4,i], J6→joint[5,i] *)
	 *
	 * In simatic-ax the target struct is Trajectory / TrajectoryPoint (see Trajectory.st).
	 * In Codesys adapt to the application DeviceFacade trajectory buffer.
	 *)

	(*
	IF jsonKey = "tempSetpoint" THEN
	    dev.tempSetpoint := TO_REAL(jsonValue.value.lrValue);
	ELSIF jsonKey = "tempHysteresis" THEN
	    dev.tempHysteresis := TO_REAL(jsonValue.value.lrValue);
	ELSIF jsonKey = "coldGlycolEnableRequest" THEN
	    dev.coldGroupEnableRequest := jsonValue.value.xValue;
	ELSIF jsonKey = "workEffort.workEffortName" THEN
	    workEffort.workEffortName := LEFT(TO_STRING(jsonValue.value.wsValue), 255);
		...
	END_IF;
	*)
	END_FUNCTION_BLOCK

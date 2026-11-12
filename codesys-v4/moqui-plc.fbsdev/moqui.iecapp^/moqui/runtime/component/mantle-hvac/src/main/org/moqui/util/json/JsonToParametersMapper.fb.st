FUNCTION_BLOCK JsonToParametersMapper
	
	VAR_INPUT
	    jsonKey : WSTRING(255) := "";
	    jsonValue : JSON.JSONElement;
	END_VAR

	(* Args validation *)
	IF (jsonKey = "") THEN RETURN; END_IF;

	(* Approved HVAC live-parameter write surface. Keep keys aligned with
	 * HVACDemoData.xml DeviceRequestItem.requestItemName values.
	 * Unknown envelope fields such as parameterId and numericValue are ignored. *)
	IF jsonKey = "tempSetpoint" THEN
		ec.dev.tempSetpoint := TO_REAL(jsonValue.value.lrValue);
	ELSIF jsonKey = "tempHysteresis" THEN
		ec.dev.tempHysteresis := TO_REAL(jsonValue.value.lrValue);
	ELSIF jsonKey = "tempMin" THEN
		ec.dev.tempMin := TO_REAL(jsonValue.value.lrValue);
	ELSIF jsonKey = "tempMax" THEN
		ec.dev.tempMax := TO_REAL(jsonValue.value.lrValue);
	ELSIF jsonKey = "rhSetpoint" THEN
		ec.dev.rhSetpoint := TO_REAL(jsonValue.value.lrValue);
	ELSIF jsonKey = "rhHysteresis" THEN
		ec.dev.rhHysteresis := TO_REAL(jsonValue.value.lrValue);
	ELSIF jsonKey = "rhMin" THEN
		ec.dev.rhMin := TO_REAL(jsonValue.value.lrValue);
	ELSIF jsonKey = "rhMax" THEN
		ec.dev.rhMax := TO_REAL(jsonValue.value.lrValue);
	ELSIF jsonKey = "ductTempMin" THEN
		ec.dev.ductTempMin := TO_REAL(jsonValue.value.lrValue);
	ELSIF jsonKey = "ductTempMax" THEN
		ec.dev.ductTempMax := TO_REAL(jsonValue.value.lrValue);
	ELSIF jsonKey = "ductRhMax" THEN
		ec.dev.ductRhMax := TO_REAL(jsonValue.value.lrValue);
	ELSIF jsonKey = "setPointTimeHigh" THEN
		ec.dev.setPointTimeHigh := TO_UINT(jsonValue.value.lrValue);
	ELSIF jsonKey = "setPointTimeLow" THEN
		ec.dev.setPointTimeLow := TO_UINT(jsonValue.value.lrValue);
	ELSIF jsonKey = "processEstimatedDuration" THEN
		ec.dev.processEstimatedDuration := TO_UDINT(jsonValue.value.lrValue);
	ELSIF jsonKey = "processMinDuration" THEN
		ec.dev.processMinDuration := TO_UDINT(jsonValue.value.lrValue);
	ELSIF jsonKey = "processRemainingDuration" THEN
		ec.dev.processRemainingDuration := TO_UDINT(jsonValue.value.lrValue);
	ELSIF jsonKey = "estimatedRuntime" THEN
		ec.dev.estimatedRuntime := TO_UDINT(jsonValue.value.lrValue);
	ELSIF jsonKey = "minRuntime" THEN
		ec.dev.minRuntime := TO_UDINT(jsonValue.value.lrValue);
	ELSIF jsonKey = "estimatedBreakDuration" THEN
		ec.dev.estimatedBreakDuration := TO_UDINT(jsonValue.value.lrValue);
	ELSIF jsonKey = "minBreakDuration" THEN
		ec.dev.minBreakDuration := TO_UDINT(jsonValue.value.lrValue);
	END_IF;

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

	END_FUNCTION_BLOCK

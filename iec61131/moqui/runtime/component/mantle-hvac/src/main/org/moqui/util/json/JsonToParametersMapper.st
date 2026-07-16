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

	(* Approved HVAC live-parameter write surface. Keep keys aligned with
	 * HVACDemoData.xml DeviceRequestItem.requestItemName values.
	 * Unknown envelope fields such as parameterId and numericValue are ignored. *)
	IF jsonKey = "tempSetpoint" THEN
		dev.tempSetpoint := TO_REAL(jsonValue.value.lrValue);
	ELSIF jsonKey = "tempHysteresis" THEN
		dev.tempHysteresis := TO_REAL(jsonValue.value.lrValue);
	ELSIF jsonKey = "tempMin" THEN
		dev.tempMin := TO_REAL(jsonValue.value.lrValue);
	ELSIF jsonKey = "tempMax" THEN
		dev.tempMax := TO_REAL(jsonValue.value.lrValue);
	ELSIF jsonKey = "rhSetpoint" THEN
		dev.rhSetpoint := TO_REAL(jsonValue.value.lrValue);
	ELSIF jsonKey = "rhHysteresis" THEN
		dev.rhHysteresis := TO_REAL(jsonValue.value.lrValue);
	ELSIF jsonKey = "rhMin" THEN
		dev.rhMin := TO_REAL(jsonValue.value.lrValue);
	ELSIF jsonKey = "rhMax" THEN
		dev.rhMax := TO_REAL(jsonValue.value.lrValue);
	ELSIF jsonKey = "ductTempMin" THEN
		dev.ductTempMin := TO_REAL(jsonValue.value.lrValue);
	ELSIF jsonKey = "ductTempMax" THEN
		dev.ductTempMax := TO_REAL(jsonValue.value.lrValue);
	ELSIF jsonKey = "ductRhMax" THEN
		dev.ductRhMax := TO_REAL(jsonValue.value.lrValue);
	ELSIF jsonKey = "setPointTimeHigh" THEN
		dev.setPointTimeHigh := TO_UINT(jsonValue.value.lrValue);
	ELSIF jsonKey = "setPointTimeLow" THEN
		dev.setPointTimeLow := TO_UINT(jsonValue.value.lrValue);
	ELSIF jsonKey = "processEstimatedDuration" THEN
		dev.processEstimatedDuration := TO_UDINT(jsonValue.value.lrValue);
	ELSIF jsonKey = "processMinDuration" THEN
		dev.processMinDuration := TO_UDINT(jsonValue.value.lrValue);
	ELSIF jsonKey = "processRemainingDuration" THEN
		dev.processRemainingDuration := TO_UDINT(jsonValue.value.lrValue);
	ELSIF jsonKey = "estimatedRuntime" THEN
		dev.estimatedRuntime := TO_UDINT(jsonValue.value.lrValue);
	ELSIF jsonKey = "minRuntime" THEN
		dev.minRuntime := TO_UDINT(jsonValue.value.lrValue);
	ELSIF jsonKey = "estimatedBreakDuration" THEN
		dev.estimatedBreakDuration := TO_UDINT(jsonValue.value.lrValue);
	ELSIF jsonKey = "minBreakDuration" THEN
		dev.minBreakDuration := TO_UDINT(jsonValue.value.lrValue);
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

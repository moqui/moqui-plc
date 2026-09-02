FUNCTION_BLOCK JsonToParametersMapper
	VAR_EXTERNAL
		dev : DeviceFacade;
	END_VAR
	VAR_INPUT
		jsonKey : WSTRING(255) := "";
		jsonValue : JSON.JSONElement;
	END_VAR

	IF jsonKey = "" THEN RETURN; END_IF;

	IF jsonKey = "cbSetpoint" THEN
		dev.concentrationControllerSetpoint := TO_REAL(jsonValue.value.lrValue); (* P_REACTOR_CC_SETPOINT *)
	END_IF;
	END_FUNCTION_BLOCK

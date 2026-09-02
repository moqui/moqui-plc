FUNCTION_BLOCK JsonToParametersMapper
	VAR_EXTERNAL
		dev : DeviceFacade;
	END_VAR
	VAR_INPUT
		jsonKey : WSTRING(255) := "";
		jsonValue : JSON.JSONElement;
	END_VAR

	IF jsonKey = "" THEN RETURN; END_IF;

	IF jsonKey = "hsp" THEN
		dev.levelControllerSetpoint := TO_REAL(jsonValue.value.lrValue); (* P_TANK_LC_SETPOINT *)
	END_IF;
	END_FUNCTION_BLOCK

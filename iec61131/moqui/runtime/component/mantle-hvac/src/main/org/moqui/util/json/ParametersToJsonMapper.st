FUNCTION_BLOCK ParametersToJsonMapper
	VAR_EXTERNAL
		dev : DeviceFacade;
	END_VAR
	VAR_IN_OUT
	    jsonBuilder : JSON.JSONBuilder;
	END_VAR
	VAR_INPUT
	    rootIndex : DINT;
	END_VAR

	(* Approved HVAC live-parameter surface. Keep keys aligned with
	 * HVACDemoData.xml DeviceRequestItem.requestItemName values. *)
	jsonBuilder.SetKeyWithValue("tempSetpoint", dev.tempSetpoint, rootIndex);
	jsonBuilder.SetKeyWithValue("tempHysteresis", dev.tempHysteresis, rootIndex);
	jsonBuilder.SetKeyWithValue("tempMin", dev.tempMin, rootIndex);
	jsonBuilder.SetKeyWithValue("tempMax", dev.tempMax, rootIndex);
	jsonBuilder.SetKeyWithValue("rhSetpoint", dev.rhSetpoint, rootIndex);
	jsonBuilder.SetKeyWithValue("rhHysteresis", dev.rhHysteresis, rootIndex);
	jsonBuilder.SetKeyWithValue("rhMin", dev.rhMin, rootIndex);
	jsonBuilder.SetKeyWithValue("rhMax", dev.rhMax, rootIndex);
	jsonBuilder.SetKeyWithValue("ductTempMin", dev.ductTempMin, rootIndex);
	jsonBuilder.SetKeyWithValue("ductTempMax", dev.ductTempMax, rootIndex);
	jsonBuilder.SetKeyWithValue("ductRhMax", dev.ductRhMax, rootIndex);
	jsonBuilder.SetKeyWithValue("setPointTimeHigh", dev.setPointTimeHigh, rootIndex);
	jsonBuilder.SetKeyWithValue("setPointTimeLow", dev.setPointTimeLow, rootIndex);
	jsonBuilder.SetKeyWithValue("processEstimatedDuration", dev.processEstimatedDuration, rootIndex);
	jsonBuilder.SetKeyWithValue("processMinDuration", dev.processMinDuration, rootIndex);
	jsonBuilder.SetKeyWithValue("processRemainingDuration", dev.processRemainingDuration, rootIndex);
	jsonBuilder.SetKeyWithValue("estimatedRuntime", dev.estimatedRuntime, rootIndex);
	jsonBuilder.SetKeyWithValue("minRuntime", dev.minRuntime, rootIndex);
	jsonBuilder.SetKeyWithValue("estimatedBreakDuration", dev.estimatedBreakDuration, rootIndex);
	jsonBuilder.SetKeyWithValue("minBreakDuration", dev.minBreakDuration, rootIndex);

	(* Runtime telemetry is published alongside the configurable live surface. *)
	jsonBuilder.SetKeyWithValue("processActualDuration", dev.processActualDuration, rootIndex);
	jsonBuilder.SetKeyWithValue("actualRuntime", dev.actualRuntime, rootIndex);
	jsonBuilder.SetKeyWithValue("actualBreakDuration", dev.actualBreakDuration, rootIndex);
	jsonBuilder.SetKeyWithValue("airFlowActuatorFault", dev.airFlow.actuatorFault, rootIndex);
	END_FUNCTION_BLOCK

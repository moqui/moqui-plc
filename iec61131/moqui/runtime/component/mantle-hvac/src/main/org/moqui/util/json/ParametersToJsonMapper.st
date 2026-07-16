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

	(* Application-specific parameter-replication example (documentation only).
	 * MqttParameterPub is disabled by default. When an Application explicitly
	 * exchanges parameters with a peer PLC/Application for redundancy, generate
	 * a reviewed replication projection independently from the inbound
	 * live-parameter whitelist. Operational telemetry belongs to LogDispatcher.
	 *
	 * jsonBuilder.SetKeyWithValue("processActualDuration", dev.processActualDuration, rootIndex);
	 * jsonBuilder.SetKeyWithValue("actualRuntime", dev.actualRuntime, rootIndex);
	 * jsonBuilder.SetKeyWithValue("actualBreakDuration", dev.actualBreakDuration, rootIndex);
	 * jsonBuilder.SetKeyWithValue("airFlowActuatorFault", dev.airFlow.actuatorFault, rootIndex);
	 *)
	END_FUNCTION_BLOCK

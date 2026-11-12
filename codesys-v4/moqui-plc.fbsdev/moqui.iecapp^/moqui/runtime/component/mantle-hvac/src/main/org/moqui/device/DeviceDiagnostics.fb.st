(* Device diagnostics *)
FUNCTION_BLOCK DeviceDiagnostics
	
	VAR_INPUT
		operationType : OperatingMode := OperatingMode.Run;
	END_VAR
	VAR_OUTPUT
		error : BOOL;
	END_VAR

	error := TRUE;

	(* Signal management engine *)
	(*
	 * Prepare a fresh scan (clears the accumulated output action).
	 * Then process each device signal in priority order.
	 * ImmediateStop -> faultRequest := TRUE -> Main enters Fault state.
	 *)
	ec.dev.signalMgmt(operationType := SignalMgmtOperatingMode.Prepare);
	ec.dev.signalMgmt.operationType := SignalMgmtOperatingMode.Process;

	(* Device faults *)
	ec.dev.signalMgmt(
		loggerName := ec.dev.ahuFan.loggerName,
		code := 16#0001,
		category := SignalCategory.Alarm,
		resetPol := ResetPolicy.UnconditionedReset,
		activationCondition := ec.dev.ahuFan.invalidConfig,
		outputAction := SignalOutputAction.ImmediateStop);
	ec.dev.signalMgmt(
		loggerName := ec.dev.airFlow.loggerName,
		code := 16#0002,
		category := SignalCategory.Alarm,
		resetPol := ResetPolicy.UnconditionedReset,
		activationCondition := ec.dev.airFlow.fault,
		outputAction := SignalOutputAction.ImmediateStop);
	ec.dev.signalMgmt(
		loggerName := ec.dev.coldGlycolPump.loggerName,
		code := 16#0003,
		category := SignalCategory.Alarm,
		resetPol := ResetPolicy.UnconditionedReset,
		activationCondition := ec.dev.coldGlycolPump.fault,
		outputAction := SignalOutputAction.ImmediateStop);
	ec.dev.signalMgmt(
		loggerName := ec.dev.coldGlycolValve.loggerName,
		code := 16#0004,
		category := SignalCategory.Alarm,
		resetPol := ResetPolicy.UnconditionedReset,
		activationCondition := ec.dev.coldGlycolValve.invalidConfig,
		outputAction := SignalOutputAction.ImmediateStop);
	ec.dev.signalMgmt(
		loggerName := ec.dev.hotGlycolPump.loggerName,
		code := 16#0005,
		category := SignalCategory.Alarm,
		resetPol := ResetPolicy.UnconditionedReset,
		activationCondition := ec.dev.hotGlycolPump.fault,
		outputAction := SignalOutputAction.ImmediateStop);
	ec.dev.signalMgmt(
		loggerName := ec.dev.hotGlycolValve.loggerName,
		code := 16#0006,
		category := SignalCategory.Alarm,
		resetPol := ResetPolicy.UnconditionedReset,
		activationCondition := ec.dev.hotGlycolValve.invalidConfig,
		outputAction := SignalOutputAction.ImmediateStop);
	ec.dev.signalMgmt(
		loggerName := ec.dev.highFlowDamper.loggerName,
		code := 16#0007,
		category := SignalCategory.Alarm,
		resetPol := ResetPolicy.UnconditionedReset,
		activationCondition := ec.dev.highFlowDamper.fault,
		outputAction := SignalOutputAction.ImmediateStop);
	ec.dev.signalMgmt(
		loggerName := ec.dev.lowFlowDamper.loggerName,
		code := 16#0008,
		category := SignalCategory.Alarm,
		resetPol := ResetPolicy.UnconditionedReset,
		activationCondition := ec.dev.lowFlowDamper.fault,
		outputAction := SignalOutputAction.ImmediateStop);

	(* 
	 * Duct safety alarms - supply-air temperature limits (ImmediateStop).
	 * Air that is too hot or too cold entering the curing room can damage
	 * or contaminate the product. These alarms are always evaluated
	 * regardless of the current FSM state.
	 *)
	ec.dev.signalMgmt(
		loggerName := 'HVAC_DEMO_PLC',
		code := 16#0010,
		category := SignalCategory.Alarm,
		resetPol := ResetPolicy.UnconditionedReset,
		activationCondition := ec.dev.ductTempOverMax,
		outputAction := SignalOutputAction.ImmediateStop);
	ec.dev.signalMgmt(
		loggerName := 'HVAC_DEMO_PLC',
		code := 16#0011,
		category := SignalCategory.Alarm,
		resetPol := ResetPolicy.UnconditionedReset,
		activationCondition := ec.dev.ductTempUnderMin,
		outputAction := SignalOutputAction.ImmediateStop);

	(* Duct RH - Warning only (condensation risk, does not stop the machine) *)
	ec.dev.signalMgmt(
		loggerName := 'HVAC_DEMO_PLC',
		code := 16#0012,
		category := SignalCategory.Warning,
		resetPol := ResetPolicy.UnconditionedReset,
		activationCondition := ec.dev.ductRhOverMax,
		outputAction := SignalOutputAction.None);

	error := FALSE;
	END_FUNCTION_BLOCK

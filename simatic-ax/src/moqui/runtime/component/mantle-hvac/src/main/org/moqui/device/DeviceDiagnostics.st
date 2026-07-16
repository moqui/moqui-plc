(* Device diagnostics *)
FUNCTION_BLOCK DeviceDiagnostics
	VAR_EXTERNAL
		dev : DeviceFacade;
	END_VAR
	VAR_INPUT
		operationType : OperatingMode := OperatingMode#Run;
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
	dev.signalMgmt(operationType := SignalMgmtOperatingMode#Prepare);
	dev.signalMgmt.operationType := SignalMgmtOperatingMode#Process;

	(* Device faults *)
	dev.signalMgmt(
		loggerName := dev.ahuFan.loggerName,
		code := 16#0001,
		category := SignalCategory#Alarm,
		resetPol := ResetPolicy#UnconditionedReset,
		activationCondition := dev.ahuFan.invalidConfig,
		outputAction := DWORD#16#0002);
	dev.signalMgmt(
		loggerName := dev.airFlow.loggerName,
		code := 16#0002,
		category := SignalCategory#Alarm,
		resetPol := ResetPolicy#UnconditionedReset,
		activationCondition := dev.airFlow.fault,
		outputAction := DWORD#16#0002);
	dev.signalMgmt(
		loggerName := dev.coldGlycolPump.loggerName,
		code := 16#0003,
		category := SignalCategory#Alarm,
		resetPol := ResetPolicy#UnconditionedReset,
		activationCondition := dev.coldGlycolPump.fault,
		outputAction := DWORD#16#0002);
	dev.signalMgmt(
		loggerName := dev.coldGlycolValve.loggerName,
		code := 16#0004,
		category := SignalCategory#Alarm,
		resetPol := ResetPolicy#UnconditionedReset,
		activationCondition := dev.coldGlycolValve.invalidConfig,
		outputAction := DWORD#16#0002);
	dev.signalMgmt(
		loggerName := dev.hotGlycolPump.loggerName,
		code := 16#0005,
		category := SignalCategory#Alarm,
		resetPol := ResetPolicy#UnconditionedReset,
		activationCondition := dev.hotGlycolPump.fault,
		outputAction := DWORD#16#0002);
	dev.signalMgmt(
		loggerName := dev.hotGlycolValve.loggerName,
		code := 16#0006,
		category := SignalCategory#Alarm,
		resetPol := ResetPolicy#UnconditionedReset,
		activationCondition := dev.hotGlycolValve.invalidConfig,
		outputAction := DWORD#16#0002);
	dev.signalMgmt(
		loggerName := dev.highFlowDamper.loggerName,
		code := 16#0007,
		category := SignalCategory#Alarm,
		resetPol := ResetPolicy#UnconditionedReset,
		activationCondition := dev.highFlowDamper.fault,
		outputAction := DWORD#16#0002);
	dev.signalMgmt(
		loggerName := dev.lowFlowDamper.loggerName,
		code := 16#0008,
		category := SignalCategory#Alarm,
		resetPol := ResetPolicy#UnconditionedReset,
		activationCondition := dev.lowFlowDamper.fault,
		outputAction := DWORD#16#0002);

	(* 
	 * Duct safety alarms - supply-air temperature limits (ImmediateStop).
	 * Air that is too hot or too cold entering the curing room can damage
	 * or contaminate the product. These alarms are always evaluated
	 * regardless of the current FSM state.
	 *)
	dev.signalMgmt(
		loggerName := 'HVAC_DEMO_PLC',
		code := 16#0010,
		category := SignalCategory#Alarm,
		resetPol := ResetPolicy#UnconditionedReset,
		activationCondition := dev.ductTempOverMax,
		outputAction := DWORD#16#0002);
	dev.signalMgmt(
		loggerName := 'HVAC_DEMO_PLC',
		code := 16#0011,
		category := SignalCategory#Alarm,
		resetPol := ResetPolicy#UnconditionedReset,
		activationCondition := dev.ductTempUnderMin,
		outputAction := DWORD#16#0002);

	(* Duct RH - Warning only (condensation risk, does not stop the machine) *)
	dev.signalMgmt(
		loggerName := 'HVAC_DEMO_PLC',
		code := 16#0012,
		category := SignalCategory#Warning,
		resetPol := ResetPolicy#UnconditionedReset,
		activationCondition := dev.ductRhOverMax,
		outputAction := DWORD#16#0000);

	error := FALSE;
	END_FUNCTION_BLOCK

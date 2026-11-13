(*
 * Periodic logger for the numeric parameters of the HVAC Application.
 *
 * Physical signal logging belongs to InputSignalUpdate and OutputSignalUpdate.
 * This block logs the logical values exposed through DeviceFacade. The source
 * of each event is the exact moqui.math.Parameter.parameterId from
	 * HVACDemoData.xml; loggerName is the owning Device.deviceId.
 *)
FUNCTION_BLOCK ParameterLogger
	
	VAR_INPUT
		operationType : OperatingMode;
	END_VAR
	VAR
		logger : LoggerFacade;
	END_VAR
	VAR CONSTANT
		componentName : STRING := 'HVAC_DEMO_PLC';
	END_VAR

	(* Log only one snapshot per minute, independently of the PLC task cycle. *)
	IF (operationType <> OperatingMode.Run) OR NOT ec.clks.clock1minute THEN RETURN; END_IF;

	logger.enable := TRUE;
	logger.loggerName := componentName;
	logger.payloadType := LogPayloadType.Numeric;
	logger.level := LogLevel.Info;

	(* Process setpoints and limits. *)
	logger(source := 'HvacTempSetpoint', numericValue := TO_LREAL(ec.dev.tempSetpoint));
	logger(source := 'HvacTempHysteresis', numericValue := TO_LREAL(ec.dev.tempHysteresis));
	logger(source := 'HvacTempMin', numericValue := TO_LREAL(ec.dev.tempMin));
	logger(source := 'HvacTempMax', numericValue := TO_LREAL(ec.dev.tempMax));
	logger(source := 'HvacRhSetpoint', numericValue := TO_LREAL(ec.dev.rhSetpoint));
	logger(source := 'HvacRhHysteresis', numericValue := TO_LREAL(ec.dev.rhHysteresis));
	logger(source := 'HvacRhMin', numericValue := TO_LREAL(ec.dev.rhMin));
	logger(source := 'HvacRhMax', numericValue := TO_LREAL(ec.dev.rhMax));
	logger(source := 'HvacDuctTempMin', numericValue := TO_LREAL(ec.dev.ductTempMin));
	logger(source := 'HvacDuctTempMax', numericValue := TO_LREAL(ec.dev.ductTempMax));
	logger(source := 'HvacDuctRhMax', numericValue := TO_LREAL(ec.dev.ductRhMax));

	(* Application timing parameters and runtime counters. *)
	logger(source := 'HvacSetPointTimeHigh', numericValue := TO_LREAL(ec.dev.setPointTimeHigh));
	logger(source := 'HvacSetPointTimeLow', numericValue := TO_LREAL(ec.dev.setPointTimeLow));
	logger(source := 'HvacEstimatedRuntime', numericValue := TO_LREAL(ec.dev.estimatedRuntime));
	logger(source := 'HvacMinRuntime', numericValue := TO_LREAL(ec.dev.minRuntime));
	logger(source := 'HvacEstimatedBreakDuration', numericValue := TO_LREAL(ec.dev.estimatedBreakDuration));
	logger(source := 'HvacMinBreakDuration', numericValue := TO_LREAL(ec.dev.minBreakDuration));
	logger(source := 'HvacProcessEstimatedDuration', numericValue := TO_LREAL(ec.dev.processEstimatedDuration));
	logger(source := 'HvacProcessMinDuration', numericValue := TO_LREAL(ec.dev.processMinDuration));
	logger(source := 'HvacProcessRemainingDuration', numericValue := TO_LREAL(ec.dev.processRemainingDuration));
	logger(source := 'HvacProcessActualDuration', numericValue := TO_LREAL(ec.dev.processActualDuration));
	logger(source := 'HvacActualRuntime', numericValue := TO_LREAL(ec.dev.actualRuntime));
	logger(source := 'HvacActualBreakDuration', numericValue := TO_LREAL(ec.dev.actualBreakDuration));

	(* Numeric machine references. *)
	logger(source := 'HvacAhuFanSpeedSetpoint', numericValue := TO_LREAL(ec.dev.ahuFanSpeedSetpoint));
	logger(source := 'HvacAirFlowRef', numericValue := TO_LREAL(ec.dev.airFlowRef));

	(* Process measurements. *)
	logger(source := 'HvacTempFeedback', numericValue := TO_LREAL(ec.dev.tempFeedback));
	logger(source := 'HvacRhFeedback', numericValue := TO_LREAL(ec.dev.rhFeedback));
	logger(source := 'HvacDuctTempFeedback', numericValue := TO_LREAL(ec.dev.ductTempFeedback));
	logger(source := 'HvacDuctRhFeedback', numericValue := TO_LREAL(ec.dev.ductRhFeedback));
	END_FUNCTION_BLOCK

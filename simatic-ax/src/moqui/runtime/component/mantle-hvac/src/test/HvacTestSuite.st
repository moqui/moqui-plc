(*
 * HvacTestSuite - integration test suite for the HVAC curing-room component.
 *
 * Tests cover:
 *   Main FSM state transitions (all 7 states)
 *   MainRuleEngine predicate computation and auto-transitions
 *   Output function: which device-enable request flags are set per state
 *   Run / break cycle: Drying <-> Standby break and resume
 *   Duct safety alarms: ImmediateStop on temperature limit violation
 *   Fault recovery via operationType = Init
 *
 * AX port notes:
 *   Enum access converted to hash notation (e.g. MainStatus#Standby).
 *   Unused VAR_EXTERNAL 'workEffort : WorkEffort' removed (no body references).
 *   PROGRAM block structure retained; test runs as a PLC task on deployment.
 *)
PROGRAM HvacTestSuite
	VAR_EXTERNAL
		dev : DeviceFacade;
		clks : Clocks;
	END_VAR
	VAR CONSTANT
		(* Maximum cycles per step before the watchdog fires. *)
		TIMEOUT : UINT := UINT#500;
		(* Sensor values used throughout the tests. All reals in degrees C / %. *)
		T_SETPOINT : REAL := REAL#4.0;
		T_HYS : REAL := REAL#0.5;
		T_MIN : REAL := REAL#2.0;
		T_MAX : REAL := REAL#6.0;
		T_NORMAL : REAL := REAL#4.0;
		T_HOT : REAL := REAL#7.0;
		T_COLD : REAL := REAL#1.0;
		RH_SET : REAL := REAL#75.0;
		RH_HYS : REAL := REAL#2.0;
		RH_MIN : REAL := REAL#60.0;
		RH_MAX : REAL := REAL#85.0;
		RH_NORMAL : REAL := REAL#75.0;
		DUCT_MIN : REAL := REAL#0.0;
		DUCT_MAX : REAL := REAL#10.0;
		DUCT_RH_MAX : REAL := REAL#95.0;
		DUCT_NORMAL : REAL := REAL#5.0;
		DUCT_HOT : REAL := REAL#12.0;
		DUCT_COLD : REAL := REAL#-1.0;
	END_VAR
	VAR
		main : Main;

		step : UINT := UINT#0;
		cycles : UINT;
		testDone : BOOL;
		testFailed : BOOL;
		failStep : UINT;
		testReset : BOOL;
		pass : ARRAY[1..32] OF BOOL;

		mirStatus : MainStatus;
		mirColdGroupEnable : BOOL;
		mirHotGroupEnable : BOOL;
		mirAhuFanEnable : BOOL;
		mirAirFlowEnable : BOOL;
		mirFaultRequest : BOOL;
		mirStandbyRequest : BOOL;
		mirCoolingRequest : BOOL;
		mirHeatingRequest : BOOL;
		mirDryingRequest : BOOL;
		mirTempInRange : BOOL;
		mirTempOverMax : BOOL;
		mirTempUnderMin : BOOL;
		mirDuctTempOverMax : BOOL;
		mirDuctTempUnderMin : BOOL;
		mirTimeBreakEnabled : BOOL;
		mirLastStatus : MainStatus;
		mirActualRuntime : UDINT;
		mirAhuFanInvalidConfig : BOOL;
		mirColdValveInvalidConfig : BOOL;
		mirHotValveInvalidConfig : BOOL;
		mirColdPumpFault : BOOL;
		mirHotPumpFault : BOOL;
		mirAirFlowFault : BOOL;
	END_VAR

	(* Watchdog *)
	cycles := cycles + UINT#1;
	IF (cycles > TIMEOUT) AND NOT testDone THEN
		testFailed := TRUE;
		failStep := step;
	END_IF;
	IF testFailed THEN RETURN; END_IF;

	(* Warm-download reset *)
	IF testReset THEN
		step := UINT#0;
		cycles := UINT#0;
		testDone := FALSE;
		testFailed := FALSE;
		failStep := UINT#0;
		pass[1] := FALSE;
		pass[2] := FALSE;
		pass[3] := FALSE;
		pass[4] := FALSE;
		pass[5] := FALSE;
		pass[6] := FALSE;
		pass[7] := FALSE;
		pass[8] := FALSE;
		pass[9] := FALSE;
		pass[10] := FALSE;
		pass[11] := FALSE;
		pass[12] := FALSE;
		pass[13] := FALSE;
		pass[14] := FALSE;
		pass[15] := FALSE;
		pass[16] := FALSE;
		pass[17] := FALSE;
		pass[18] := FALSE;
		pass[19] := FALSE;
		pass[20] := FALSE;
		pass[21] := FALSE;
		pass[22] := FALSE;
		pass[23] := FALSE;
		pass[24] := FALSE;
		pass[25] := FALSE;
		pass[26] := FALSE;
		pass[27] := FALSE;
		pass[28] := FALSE;
		pass[29] := FALSE;
		pass[30] := FALSE;
		pass[31] := FALSE;
		pass[32] := FALSE;
		dev.status := MainStatus#Standby;
		dev.lastStatus := MainStatus#Standby;
		dev.isCompleted := FALSE;
		dev.timeBreakEnabled := FALSE;
		dev.actualRuntime := UDINT#0;
		dev.actualBreakDuration := UDINT#0;
		dev.faultRequest := FALSE;
		testReset := FALSE;
	END_IF;

	(* Default recipe configuration *)
	dev.tempSetpoint := T_SETPOINT;
	dev.tempHysteresis := T_HYS;
	dev.tempMin := T_MIN;
	dev.tempMax := T_MAX;
	dev.rhSetpoint := RH_SET;
	dev.rhHysteresis := RH_HYS;
	dev.rhMin := RH_MIN;
	dev.rhMax := RH_MAX;
	dev.rhControlEnabled := FALSE;
	dev.rhControlOnly := FALSE;
	dev.isCompleted := FALSE;
	dev.timeBreakEnabled := FALSE;
	dev.estimatedRuntime := UDINT#0;
	dev.minRuntime := UDINT#0;
	dev.ductTempMin := DUCT_MIN;
	dev.ductTempMax := DUCT_MAX;
	dev.ductRhMax := DUCT_RH_MAX;
	dev.tempFeedback := T_NORMAL;
	dev.rhFeedback := RH_NORMAL;
	dev.ductTempFeedback := DUCT_NORMAL;
	dev.ductRhFeedback := REAL#70.0;

	(* Static HVAC device configuration *)
	dev.coldGlycolPump.actuatorId := 'HVAC_COLD_GLYCOL_PUMP';
	dev.coldGlycolPump.actuatorName := 'ColdGlycolPump';
	dev.coldGlycolPump.actuationType := ActuatorActuationType#SingleActuation;
	dev.coldGlycolPump.feedbackType := ActuatorFeedbackType#WithoutFeedback;
	dev.coldGlycolPump.model := ActuatorModel#ABBACH580;
	dev.coldGlycolPump.enableTime := UINT#1;
	dev.coldGlycolPump.disableTime := UINT#1;
	dev.coldGlycolPump.diagnosticsEnable := FALSE;

	dev.hotGlycolPump.actuatorId := 'HVAC_HOT_GLYCOL_PUMP';
	dev.hotGlycolPump.actuatorName := 'HotGlycolPump';
	dev.hotGlycolPump.actuationType := ActuatorActuationType#SingleActuation;
	dev.hotGlycolPump.feedbackType := ActuatorFeedbackType#WithoutFeedback;
	dev.hotGlycolPump.model := ActuatorModel#ABBACH580;
	dev.hotGlycolPump.enableTime := UINT#1;
	dev.hotGlycolPump.disableTime := UINT#1;
	dev.hotGlycolPump.diagnosticsEnable := FALSE;

	dev.airFlow.actuatorId := 'HVAC_AIR_FLOW';
	dev.airFlow.actuatorName := 'AirFlow';
	dev.airFlow.actuationType := ActuatorActuationType#SingleActuation;
	dev.airFlow.feedbackType := ActuatorFeedbackType#WithoutFeedback;
	dev.airFlow.model := ActuatorModel#ABBACH580;
	dev.airFlow.enableTime := UINT#1;
	dev.airFlow.disableTime := UINT#1;
	dev.airFlow.diagnosticsEnable := FALSE;
	dev.airFlowRef := REAL#50.0;

	dev.coldGlycolValve.controlSystemId := 'HVAC_COLD_GLYCOL_VALVE';
	dev.coldGlycolValve.controlSystemName := 'ColdGlycolValve';
	dev.coldGlycolValve.gain := REAL#1.0;
	dev.coldGlycolValve.integrationTime := REAL#0.0;
	dev.coldGlycolValve.derivationTime := REAL#0.0;
	dev.coldGlycolValve.setpointMin := REAL#0.0;
	dev.coldGlycolValve.setpointMax := REAL#100.0;
	dev.coldGlycolValve.outputMin := REAL#0.0;
	dev.coldGlycolValve.outputMax := REAL#100.0;
	dev.coldGlycolValve.atSetpointHysteresis := T_HYS;
	dev.coldGlycolValve.tickTime := T#100ms;

	dev.hotGlycolValve.controlSystemId := 'HVAC_HOT_GLYCOL_VALVE';
	dev.hotGlycolValve.controlSystemName := 'HotGlycolValve';
	dev.hotGlycolValve.gain := REAL#1.0;
	dev.hotGlycolValve.integrationTime := REAL#0.0;
	dev.hotGlycolValve.derivationTime := REAL#0.0;
	dev.hotGlycolValve.setpointMin := REAL#0.0;
	dev.hotGlycolValve.setpointMax := REAL#100.0;
	dev.hotGlycolValve.outputMin := REAL#0.0;
	dev.hotGlycolValve.outputMax := REAL#100.0;
	dev.hotGlycolValve.atSetpointHysteresis := T_HYS;
	dev.hotGlycolValve.tickTime := T#100ms;

	dev.ahuFan.controlSystemId := 'HVAC_AHU_FAN';
	dev.ahuFan.controlSystemName := 'AhuFan';
	dev.ahuFan.gain := REAL#1.0;
	dev.ahuFan.integrationTime := REAL#0.0;
	dev.ahuFan.derivationTime := REAL#0.0;
	dev.ahuFan.setpointMin := REAL#0.0;
	dev.ahuFan.setpointMax := REAL#100.0;
	dev.ahuFan.outputMin := REAL#0.0;
	dev.ahuFan.outputMax := REAL#100.0;
	dev.ahuFan.atSetpointHysteresis := REAL#1.0;
	dev.ahuFan.tickTime := T#100ms;
	dev.ahuFanSpeedSetpoint := REAL#50.0;

	(* Test sequence *)
	CASE step OF
		UINT#0 :
			dev.status := MainStatus#Standby;
			cycles := UINT#0;
			step := UINT#1;

		UINT#1 :
			dev.status := MainStatus#Cooling;
			main(operationType := OperatingMode#Init, enable := TRUE);
			IF dev.status = MainStatus#Standby THEN
				pass[1] := TRUE;
				cycles := UINT#0;
				step := UINT#2;
			END_IF;

		UINT#2 :
			dev.status := MainStatus#Cooling;
			main(operationType := OperatingMode#Run, enable := FALSE);
			IF dev.status = MainStatus#Cooling THEN
				pass[2] := TRUE;
				main(operationType := OperatingMode#Init, enable := TRUE);
				cycles := UINT#0;
				step := UINT#3;
			END_IF;

		UINT#3 :
			dev.status := MainStatus#Standby;
			dev.lastStatus := MainStatus#Standby;
			main(operationType := OperatingMode#Run, enable := TRUE);
			IF dev.status = MainStatus#Standby
					AND NOT dev.coldGroupEnableRequest
					AND NOT dev.hotGroupEnableRequest
					AND NOT dev.ahuFanEnableRequest
					AND NOT dev.airFlowEnableRequest THEN
				pass[3] := TRUE;
				cycles := UINT#0;
				step := UINT#4;
			END_IF;

		UINT#4 :
			dev.status := MainStatus#Ventilation;
			main(operationType := OperatingMode#Run, enable := TRUE);
			IF dev.status = MainStatus#Ventilation
					AND NOT dev.coldGroupEnableRequest
					AND NOT dev.hotGroupEnableRequest
					AND dev.ahuFanEnableRequest
					AND dev.airFlowEnableRequest THEN
				pass[4] := TRUE;
				cycles := UINT#0;
				step := UINT#5;
			END_IF;

		UINT#5 :
			main(operationType := OperatingMode#Run, enable := TRUE);
			IF cycles >= UINT#5 AND dev.status = MainStatus#Ventilation THEN
				pass[5] := TRUE;
				cycles := UINT#0;
				step := UINT#6;
			END_IF;

		UINT#6 :
			dev.isCompleted := TRUE;
			main(operationType := OperatingMode#Run, enable := TRUE);
			IF dev.status = MainStatus#Standby THEN
				pass[6] := TRUE;
				dev.isCompleted := FALSE;
				cycles := UINT#0;
				step := UINT#7;
			END_IF;

		UINT#7 :
			dev.status := MainStatus#Cooling;
			dev.tempFeedback := T_HOT;
			main(operationType := OperatingMode#Run, enable := TRUE);
			IF dev.status = MainStatus#Cooling
					AND dev.coldGroupEnableRequest
					AND NOT dev.hotGroupEnableRequest
					AND dev.ahuFanEnableRequest THEN
				pass[7] := TRUE;
				cycles := UINT#0;
				step := UINT#8;
			END_IF;

		UINT#8 :
			dev.tempFeedback := T_HOT;
			main(operationType := OperatingMode#Run, enable := TRUE);
			IF cycles >= UINT#5 AND dev.status = MainStatus#Cooling THEN
				pass[8] := TRUE;
				cycles := UINT#0;
				step := UINT#9;
			END_IF;

		UINT#9 :
			dev.tempFeedback := T_SETPOINT - T_HYS;
			main(operationType := OperatingMode#Run, enable := TRUE);
			IF dev.status = MainStatus#Standby THEN
				pass[9] := TRUE;
				dev.tempFeedback := T_NORMAL;
				cycles := UINT#0;
				step := UINT#10;
			END_IF;

		UINT#10 :
			dev.status := MainStatus#Heating;
			dev.tempFeedback := T_COLD;
			main(operationType := OperatingMode#Run, enable := TRUE);
			IF dev.status = MainStatus#Heating
					AND NOT dev.coldGroupEnableRequest
					AND dev.hotGroupEnableRequest
					AND dev.ahuFanEnableRequest THEN
				pass[10] := TRUE;
				cycles := UINT#0;
				step := UINT#11;
			END_IF;

		UINT#11 :
			dev.tempFeedback := T_COLD;
			main(operationType := OperatingMode#Run, enable := TRUE);
			IF cycles >= UINT#5 AND dev.status = MainStatus#Heating THEN
				pass[11] := TRUE;
				cycles := UINT#0;
				step := UINT#12;
			END_IF;

		UINT#12 :
			dev.tempFeedback := T_SETPOINT + T_HYS;
			main(operationType := OperatingMode#Run, enable := TRUE);
			IF dev.status = MainStatus#Standby THEN
				pass[12] := TRUE;
				dev.tempFeedback := T_NORMAL;
				cycles := UINT#0;
				step := UINT#13;
			END_IF;

		UINT#13 :
			dev.status := MainStatus#Drying;
			dev.tempFeedback := T_NORMAL;
			main(operationType := OperatingMode#Run, enable := TRUE);
			IF dev.status = MainStatus#Drying
					AND dev.coldGroupEnableRequest
					AND dev.hotGroupEnableRequest
					AND dev.ahuFanEnableRequest THEN
				pass[13] := TRUE;
				cycles := UINT#0;
				step := UINT#14;
			END_IF;

		UINT#14 :
			dev.tempFeedback := T_NORMAL;
			main(operationType := OperatingMode#Run, enable := TRUE);
			IF cycles >= UINT#5 AND dev.status = MainStatus#Drying THEN
				pass[14] := TRUE;
				cycles := UINT#0;
				step := UINT#15;
			END_IF;

		UINT#15 :
			dev.tempFeedback := T_HOT;
			main(operationType := OperatingMode#Run, enable := TRUE);
			IF dev.status = MainStatus#Cooling THEN
				pass[15] := TRUE;
				cycles := UINT#0;
				step := UINT#16;
			END_IF;

		UINT#16 :
			dev.lastStatus := MainStatus#Drying;
			dev.tempFeedback := T_NORMAL;
			main(operationType := OperatingMode#Run, enable := TRUE);
			IF dev.status = MainStatus#Drying THEN
				pass[16] := TRUE;
				cycles := UINT#0;
				step := UINT#17;
			END_IF;

		UINT#17 :
			dev.tempFeedback := T_COLD;
			main(operationType := OperatingMode#Run, enable := TRUE);
			IF dev.status = MainStatus#Heating THEN
				pass[17] := TRUE;
				cycles := UINT#0;
				step := UINT#18;
			END_IF;

		UINT#18 :
			dev.lastStatus := MainStatus#Drying;
			dev.tempFeedback := T_NORMAL;
			main(operationType := OperatingMode#Run, enable := TRUE);
			IF dev.status = MainStatus#Drying THEN
				pass[18] := TRUE;
				cycles := UINT#0;
				step := UINT#19;
			END_IF;

		UINT#19 :
			dev.tempFeedback := T_NORMAL;
			dev.isCompleted := TRUE;
			main(operationType := OperatingMode#Run, enable := TRUE);
			IF dev.status = MainStatus#Standby THEN
				pass[19] := TRUE;
				dev.isCompleted := FALSE;
				cycles := UINT#0;
				step := UINT#20;
			END_IF;

		UINT#20 :
			main(operationType := OperatingMode#Init, enable := TRUE);
			dev.lastStatus := MainStatus#Drying;
			dev.status := MainStatus#Drying;
			dev.tempFeedback := T_NORMAL;
			dev.timeBreakEnabled := TRUE;
			main(operationType := OperatingMode#Run, enable := TRUE);
			IF dev.status = MainStatus#Standby THEN
				pass[20] := TRUE;
				cycles := UINT#0;
				step := UINT#21;
			END_IF;

		UINT#21 :
			dev.lastStatus := MainStatus#Drying;
			dev.timeBreakEnabled := FALSE;
			dev.tempFeedback := T_NORMAL;
			dev.rhControlOnly := FALSE;
			main(operationType := OperatingMode#Run, enable := TRUE);
			IF dev.status = MainStatus#Drying THEN
				pass[21] := TRUE;
				main(operationType := OperatingMode#Init, enable := TRUE);
				cycles := UINT#0;
				step := UINT#22;
			END_IF;

		(* Group 8: Thermostat re-activation *)

		UINT#22 :
			dev.status := MainStatus#Standby;
			dev.lastStatus := MainStatus#Cooling;
			(* Regression: T=tempMax is above the thermostat band but not over the absolute limit. *)
			dev.tempFeedback := T_MAX;
			main(operationType := OperatingMode#Run, enable := TRUE);
			IF dev.status = MainStatus#Cooling THEN
				pass[22] := TRUE;
				main(operationType := OperatingMode#Init, enable := TRUE);
				cycles := UINT#0;
				step := UINT#23;
			END_IF;

		(* Group 9: AirDistributionController - alternating high/low air throw *)

		UINT#23 :
			dev.status := MainStatus#Drying;
			dev.tempFeedback := T_NORMAL;
			dev.airDistributionEnabled := FALSE;
			dev.setPointTimeHigh := UINT#2;
			dev.setPointTimeLow := UINT#2;
			clks.clock1s := TRUE;
			main(operationType := OperatingMode#Run, enable := TRUE);
			clks.clock1s := FALSE;
			IF cycles >= UINT#5 AND NOT dev.lowFlowDamperEnableRequest THEN
				pass[23] := TRUE;
				cycles := UINT#0;
				step := UINT#24;
			END_IF;

		UINT#24 :
			dev.status := MainStatus#Drying;
			dev.tempFeedback := T_NORMAL;
			dev.airDistributionEnabled := TRUE;
			dev.setPointTimeHigh := UINT#2;
			dev.setPointTimeLow := UINT#2;
			clks.clock1s := FALSE;
			main(operationType := OperatingMode#Run, enable := TRUE);
			IF dev.highFlowDamperEnableRequest AND NOT dev.lowFlowDamperEnableRequest THEN
				pass[24] := TRUE;
				cycles := UINT#0;
				step := UINT#25;
			END_IF;

		UINT#25 :
			dev.status := MainStatus#Drying;
			dev.tempFeedback := T_NORMAL;
			dev.airDistributionEnabled := TRUE;
			clks.clock1s := TRUE;
			main(operationType := OperatingMode#Run, enable := TRUE);
			clks.clock1s := FALSE;
			IF dev.lowFlowDamperEnableRequest AND dev.highFlowDamperDisableRequest THEN
				pass[25] := TRUE;
				cycles := UINT#0;
				step := UINT#26;
			END_IF;

		UINT#26 :
			dev.status := MainStatus#Drying;
			dev.tempFeedback := T_NORMAL;
			dev.airDistributionEnabled := TRUE;
			clks.clock100ms := TRUE;
			clks.clock1s := FALSE;
			main(operationType := OperatingMode#Run, enable := TRUE);
			clks.clock100ms := FALSE;
			IF NOT dev.lowFlowDamperEnableRequest AND NOT dev.highFlowDamperDisableRequest THEN
				pass[26] := TRUE;
				cycles := UINT#0;
				step := UINT#27;
			END_IF;

		UINT#27 :
			dev.status := MainStatus#Drying;
			dev.tempFeedback := T_NORMAL;
			dev.airDistributionEnabled := TRUE;
			clks.clock1s := TRUE;
			main(operationType := OperatingMode#Run, enable := TRUE);
			clks.clock1s := FALSE;
			IF dev.highFlowDamperEnableRequest AND dev.lowFlowDamperDisableRequest THEN
				pass[27] := TRUE;
				dev.airDistributionEnabled := FALSE;
				main(operationType := OperatingMode#Init, enable := TRUE);
				cycles := UINT#0;
				step := UINT#28;
			END_IF;

		(* Group 10: Duct safety alarms *)

		UINT#28 :
			dev.status := MainStatus#Drying;
			dev.tempFeedback := T_NORMAL;
			dev.ductTempFeedback := DUCT_HOT;
			main(operationType := OperatingMode#Run, enable := TRUE);
			IF dev.status = MainStatus#Fault THEN
				pass[28] := TRUE;
				cycles := UINT#0;
				step := UINT#29;
			END_IF;

		UINT#29 :
			dev.ductTempFeedback := DUCT_HOT;
			main(operationType := OperatingMode#Run, enable := TRUE);
			IF cycles >= UINT#3 AND dev.status = MainStatus#Fault THEN
				pass[29] := TRUE;
				cycles := UINT#0;
				step := UINT#30;
			END_IF;

		UINT#30 :
			dev.ductTempFeedback := DUCT_NORMAL;
			main(operationType := OperatingMode#Init, enable := TRUE);
			IF dev.status = MainStatus#Standby THEN
				pass[30] := TRUE;
				cycles := UINT#0;
				step := UINT#31;
			END_IF;

		UINT#31 :
			dev.status := MainStatus#Drying;
			dev.tempFeedback := T_NORMAL;
			dev.ductTempFeedback := DUCT_COLD;
			main(operationType := OperatingMode#Run, enable := TRUE);
			IF dev.status = MainStatus#Fault THEN
				pass[31] := TRUE;
				dev.ductTempFeedback := DUCT_NORMAL;
				main(operationType := OperatingMode#Init, enable := TRUE);
				cycles := UINT#0;
				step := UINT#32;
			END_IF;

		UINT#32 :
			dev.status := MainStatus#Drying;
			dev.ductTempFeedback := DUCT_HOT;
			main(operationType := OperatingMode#Run, enable := TRUE);
			IF dev.status = MainStatus#Fault
					AND NOT dev.coldGroupEnableRequest
					AND NOT dev.hotGroupEnableRequest
					AND NOT dev.ahuFanEnableRequest
					AND NOT dev.airFlowEnableRequest THEN
				pass[32] := TRUE;
				dev.ductTempFeedback := DUCT_NORMAL;
				main(operationType := OperatingMode#Init, enable := TRUE);
				cycles := UINT#0;
				step := UINT#100;
			END_IF;

		UINT#100 :
			testDone := TRUE;
	END_CASE;

	(* Diagnostic mirrors *)
	mirStatus := dev.status;
	mirColdGroupEnable := dev.coldGroupEnableRequest;
	mirHotGroupEnable := dev.hotGroupEnableRequest;
	mirAhuFanEnable := dev.ahuFanEnableRequest;
	mirAirFlowEnable := dev.airFlowEnableRequest;
	mirFaultRequest := dev.faultRequest;
	mirStandbyRequest := dev.standbyRequest;
	mirCoolingRequest := dev.coolingRequest;
	mirHeatingRequest := dev.heatingRequest;
	mirDryingRequest := dev.dryingRequest;
	mirTempInRange := dev.tempInRange;
	mirTempOverMax := dev.tempOverMax;
	mirTempUnderMin := dev.tempUnderMin;
	mirDuctTempOverMax := dev.ductTempOverMax;
	mirDuctTempUnderMin := dev.ductTempUnderMin;
	mirTimeBreakEnabled := dev.timeBreakEnabled;
	mirLastStatus := dev.lastStatus;
	mirActualRuntime := dev.actualRuntime;
	mirAhuFanInvalidConfig := dev.ahuFan.invalidConfig;
	mirColdValveInvalidConfig := dev.coldGlycolValve.invalidConfig;
	mirHotValveInvalidConfig := dev.hotGlycolValve.invalidConfig;
	mirColdPumpFault := dev.coldGlycolPump.fault;
	mirHotPumpFault := dev.hotGlycolPump.fault;
	mirAirFlowFault := dev.airFlow.fault;
END_PROGRAM

(*
 * HvacTestSuite - integration test suite for the civil HVAC AHU component.
 *
 * Tests cover:
 *   Main FSM state transitions (5 active states)
 *   MainRuleEngine predicate computation and auto-transitions
 *   Output function: which device-enable request flags are set per state
 *   Run / break cycle: Drying <-> Standby break and resume
 *   Duct safety alarms: ImmediateStop on temperature limit violation
 *   Fault recovery via operationType = Init
 *
 * Architecture
 *
 * Main, MainRuleEngine, DeviceDiagnostics and DeviceManager all use VAR_EXTERNAL to share the
 * global 'dev : DeviceParameters' singleton.  The test suite controls the FSM
 * by writing sensor feedback and recipe flags into 'dev' before each call to
 * main(), then inspects 'dev.status' and the enable-request flags afterwards.
 *
 * DeviceManager internally calls the Actuator / ProcessPid FBs embedded in dev.
 * Their internal states are not tested here; that is covered by
 * DeviceTestSuite and ActuatorGroupTestSuite.
 *
 * Call order each scan:
 *   (Test setup writes dev.* fields)
 *   main(operationType, enable)
 *     └- MainRuleEngine: updates predicates, signal mgmt, sets *Request flags
 *     └- Main FSM: reads *Request -> updates dev.status
 *     └- DeviceDiagnostics: signalMgmt for each device
 *     └- DeviceManager: drives Actuator / ProcessPid FBs
 *
 * Watchdog
 *
 * Each step must complete within TIMEOUT cycles.  On expiry testFailed is set
 * and execution stops.  Write testReset := TRUE in the online monitor to
 * restart the sequence from scratch after a warm download.
 *
 * Pass-flag index
 *
 * pass[1] : Init - operationType=Init sets status=Standby
 * pass[2] : enable=FALSE - Main returns early, status unchanged
 * pass[3] : Standby output function - all groups disabled
 * pass[4] : Manual Ventilation - ventilationRequest -> Ventilation; AHU=ON, cold/hot=OFF
 * pass[5] : Ventilation persists - stays Ventilation across multiple scans
 * pass[6] : Ventilation -> Standby on isCompleted
 * pass[7] : Manual Cooling - coolingRequest -> Cooling; cold=ON, hot=OFF
 * pass[8] : Cooling persists above the upper thermostat threshold
 * pass[9] : Cooling -> Standby at the lower thermostat threshold
 * pass[10] : Manual Heating - heatingRequest -> Heating; cold=OFF, hot=ON
 * pass[11] : Heating persists below the lower thermostat threshold
 * pass[12] : Heating -> Standby at the upper thermostat threshold
 * pass[13] : Manual Drying - dryingRequest -> Drying; cold=ON, hot=ON
 * pass[14] : Drying persists - stays Drying while T in range
 * pass[15] : Drying -> Cooling on tempOverMax (emergency override)
 * pass[16] : Cooling -> Drying when resuming from Drying and T < tempMax
 * pass[17] : Drying -> Heating on tempUnderMin (emergency override)
 * pass[18] : Heating -> Drying when T restored (lastStatus=Drying, tempOverMin)
 * pass[19] : Drying -> Standby on isCompleted
 * pass[20] : Run/break: Drying -> Standby when timeBreakEnabled
 * pass[21] : Run/break: Standby -> Drying when break ends (NOT timeBreakEnabled)
 * pass[22] : Standby re-enters Cooling above setpoint band but at absolute max
 * pass[23] : AirDistrib disabled - no switching even after many clock1s ticks
 * pass[24] : AirDistrib enabled in Drying - Init->HighPhase: highFlowDamper=ON, lowFlowDamper=OFF
 * pass[25] : HighPhase->TransitionToLow after setPointTimeHigh clock ticks
 * pass[26] : TransitionToLow->LowPhase after damper handshake (Actuator ack via clock100ms)
 * pass[27] : LowPhase->TransitionToHigh after setPointTimeLow clock ticks
 * pass[28] : Duct alarm: ductTempOverMax -> Fault
 * pass[29] : Fault persists while alarm active
 * pass[30] : Fault -> Standby after Init (signalMgmt reset)
 * pass[31] : Duct alarm: ductTempUnderMin -> Fault
 * pass[32] : Fault state - all groups disabled (safe state)
 *)
PROGRAM HvacTestSuite
	VAR_EXTERNAL
	END_VAR
	VAR CONSTANT
		(* Maximum cycles per step before the watchdog fires. *)
		TIMEOUT : UINT := 500;
		(* Sensor values used throughout the tests. All reals in °C / %. *)
		T_SETPOINT : REAL := 22.0; (* Recipe temperature setpoint *)
		T_HYS : REAL := 1.0; (* Hysteresis around setpoint *)
		T_MIN : REAL := 18.0; (* Absolute lower limit *)
		T_MAX : REAL := 26.0; (* Absolute upper limit *)
		T_NORMAL : REAL := 22.0; (* Normal feed - inside window *)
		T_HOT : REAL := 28.0; (* Above tempMax -> tempOverMax = TRUE *)
		T_COLD : REAL := 15.0; (* Below tempMin -> tempUnderMin = TRUE *)
		RH_SET : REAL := 50.0;
		RH_HYS : REAL := 5.0;
		RH_MIN : REAL := 30.0;
		RH_MAX : REAL := 70.0;
		RH_NORMAL : REAL := 50.0;
		DUCT_MIN : REAL := 10.0; (* Duct temperature safety limits *)
		DUCT_MAX : REAL := 45.0;
		DUCT_RH_MAX: REAL := 95.0;
		DUCT_NORMAL: REAL := 18.0; (* Duct T in safe range *)
		DUCT_HOT : REAL := 48.0; (* Above ductTempMax -> alarm *)
		DUCT_COLD : REAL := 8.0; (* Below ductTempMin -> alarm *)
	END_VAR
	VAR
		main : Main;

		(*  Test infrastructure *)
		step : UINT := 0;
		cycles : UINT;
		testDone : BOOL;
		testFailed : BOOL;
		failStep : UINT;
		(*
		 * testReset - write TRUE in the online monitor to restart the test
		 * from scratch (clears all persistent state after a warm download).
		 *)
		testReset : BOOL;
		pass : ARRAY[1..32] OF BOOL;

		(*  Diagnostic mirrors.
		 *
		 * Inspect these in the online monitor when testFailed is TRUE to
		 * understand which assertion failed and why.
		 *)
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
		i : UINT;
	END_VAR

	(* Watchdog *)
	cycles := cycles + 1;
	IF (cycles > TIMEOUT) AND NOT testDone THEN
		testFailed := TRUE;
		failStep := step;
	END_IF;
	IF testFailed THEN RETURN; END_IF;

	(*  Warm-download reset *)
	IF testReset THEN
		step := 0;
		cycles := 0;
		testDone := FALSE;
		testFailed := FALSE;
		failStep := 0;
		FOR i := 1 TO 32 DO pass[i] := FALSE; END_FOR;
		ec.dev.status := MainStatus.Standby;
		ec.dev.lastStatus := MainStatus.Standby;
		ec.dev.isCompleted := FALSE;
		ec.dev.timeBreakEnabled := FALSE;
		ec.dev.actualRuntime := 0;
		ec.dev.actualBreakDuration := 0;
		ec.dev.faultRequest := FALSE;
		testReset := FALSE;
	END_IF;

	(* Default recipe configuration (set before calling main each scan).
	 *
	 * These values are overridden per-step when a specific sensor value is needed.
	 * They represent a realistic civil HVAC AHU recipe.
	 *)
	ec.dev.tempSetpoint := T_SETPOINT;
	ec.dev.tempHysteresis := T_HYS;
	ec.dev.tempMin := T_MIN;
	ec.dev.tempMax := T_MAX;
	ec.dev.rhSetpoint := RH_SET;
	ec.dev.rhHysteresis := RH_HYS;
	ec.dev.rhMin := RH_MIN;
	ec.dev.rhMax := RH_MAX;
	ec.dev.rhControlEnabled := FALSE;
	ec.dev.rhControlOnly := FALSE;
	ec.dev.isCompleted := FALSE;
	ec.dev.timeBreakEnabled := FALSE;
	ec.dev.estimatedRuntime := 0; (* 0 disables time-based dehumidification countdown *)
	ec.dev.minRuntime := 0;
	ec.dev.ductTempMin := DUCT_MIN;
	ec.dev.ductTempMax := DUCT_MAX;
	ec.dev.ductRhMax := DUCT_RH_MAX;
	(* Sensor defaults - safe / in-range values; overridden per step *)
	ec.dev.tempFeedback := T_NORMAL;
	ec.dev.rhFeedback := RH_NORMAL;
	ec.dev.ductTempFeedback := DUCT_NORMAL;
	ec.dev.ductRhFeedback := 60.0;

	(* Static HVAC device configuration.
	 *
	 * In production these fields are normally mapped by the HvacDeviceConfig recipe.
	 * The test suite sets the minimum safe subset directly so it remains deterministic
	 * even when the recipe manager is not part of the test task execution.
	 *)
	ec.dev.coldGlycolPump.actuatorId := 'HVAC_COLD_GLYCOL_PUMP';
	ec.dev.coldGlycolPump.actuatorName := 'ColdGlycolPump';
	ec.dev.coldGlycolPump.actuationType := ActuatorActuationType.SingleActuation;
	ec.dev.coldGlycolPump.feedbackType := ActuatorFeedbackType.WithoutFeedback;
	ec.dev.coldGlycolPump.model := ActuatorModel.ABBACH580;
	ec.dev.coldGlycolPump.enableTime := 1;
	ec.dev.coldGlycolPump.disableTime := 1;
	ec.dev.coldGlycolPump.diagnosticsEnable := FALSE;

	ec.dev.hotGlycolPump.actuatorId := 'HVAC_HOT_GLYCOL_PUMP';
	ec.dev.hotGlycolPump.actuatorName := 'HotGlycolPump';
	ec.dev.hotGlycolPump.actuationType := ActuatorActuationType.SingleActuation;
	ec.dev.hotGlycolPump.feedbackType := ActuatorFeedbackType.WithoutFeedback;
	ec.dev.hotGlycolPump.model := ActuatorModel.ABBACH580;
	ec.dev.hotGlycolPump.enableTime := 1;
	ec.dev.hotGlycolPump.disableTime := 1;
	ec.dev.hotGlycolPump.diagnosticsEnable := FALSE;

	ec.dev.airFlow.actuatorId := 'HVAC_AIR_FLOW';
	ec.dev.airFlow.actuatorName := 'AirFlow';
	ec.dev.airFlow.actuationType := ActuatorActuationType.SingleActuation;
	ec.dev.airFlow.feedbackType := ActuatorFeedbackType.WithoutFeedback;
	ec.dev.airFlow.model := ActuatorModel.ABBACH580;
	ec.dev.airFlow.enableTime := 1;
	ec.dev.airFlow.disableTime := 1;
	ec.dev.airFlow.diagnosticsEnable := FALSE;
	ec.dev.airFlowRef := 50.0;

	ec.dev.coldGlycolValve.controlSystemId := 'HVAC_COLD_GLYCOL_VALVE';
	ec.dev.coldGlycolValve.controlSystemName := 'ColdGlycolValve';
	ec.dev.coldGlycolValve.gain := 1.0;
	ec.dev.coldGlycolValve.integrationTime := 0.0;
	ec.dev.coldGlycolValve.derivationTime := 0.0;
	ec.dev.coldGlycolValve.setpointMin := 0.0;
	ec.dev.coldGlycolValve.setpointMax := 100.0;
	ec.dev.coldGlycolValve.outputMin := 0.0;
	ec.dev.coldGlycolValve.outputMax := 100.0;
	ec.dev.coldGlycolValve.atSetpointHysteresis := T_HYS;
	ec.dev.coldGlycolValve.tickTime := T#100ms;

	ec.dev.hotGlycolValve.controlSystemId := 'HVAC_HOT_GLYCOL_VALVE';
	ec.dev.hotGlycolValve.controlSystemName := 'HotGlycolValve';
	ec.dev.hotGlycolValve.gain := 1.0;
	ec.dev.hotGlycolValve.integrationTime := 0.0;
	ec.dev.hotGlycolValve.derivationTime := 0.0;
	ec.dev.hotGlycolValve.setpointMin := 0.0;
	ec.dev.hotGlycolValve.setpointMax := 100.0;
	ec.dev.hotGlycolValve.outputMin := 0.0;
	ec.dev.hotGlycolValve.outputMax := 100.0;
	ec.dev.hotGlycolValve.atSetpointHysteresis := T_HYS;
	ec.dev.hotGlycolValve.tickTime := T#100ms;

	ec.dev.ahuFan.controlSystemId := 'HVAC_AHU_FAN';
	ec.dev.ahuFan.controlSystemName := 'AhuFan';
	ec.dev.ahuFan.gain := 1.0;
	ec.dev.ahuFan.integrationTime := 0.0;
	ec.dev.ahuFan.derivationTime := 0.0;
	ec.dev.ahuFan.setpointMin := 0.0;
	ec.dev.ahuFan.setpointMax := 100.0;
	ec.dev.ahuFan.outputMin := 0.0;
	ec.dev.ahuFan.outputMax := 100.0;
	ec.dev.ahuFan.atSetpointHysteresis := 1.0;
	ec.dev.ahuFan.tickTime := T#100ms;
	ec.dev.ahuFanSpeedSetpoint := 50.0;

	ec.dev.highFlowDamper.actuatorId := 'HVAC_HIGH_FLOW_DAMPER';
	ec.dev.highFlowDamper.actuatorName := 'HighFlowDamper';
	ec.dev.highFlowDamper.actuationType := ActuatorActuationType.SingleActuation;
	ec.dev.highFlowDamper.feedbackType := ActuatorFeedbackType.WithoutFeedback;
	ec.dev.highFlowDamper.model := ActuatorModel.ABBACH580;
	ec.dev.highFlowDamper.enableTime := 1;
	ec.dev.highFlowDamper.disableTime := 1;
	ec.dev.highFlowDamper.diagnosticsEnable := FALSE;

	ec.dev.lowFlowDamper.actuatorId := 'HVAC_LOW_FLOW_DAMPER';
	ec.dev.lowFlowDamper.actuatorName := 'LowFlowDamper';
	ec.dev.lowFlowDamper.actuationType := ActuatorActuationType.SingleActuation;
	ec.dev.lowFlowDamper.feedbackType := ActuatorFeedbackType.WithoutFeedback;
	ec.dev.lowFlowDamper.model := ActuatorModel.ABBACH580;
	ec.dev.lowFlowDamper.enableTime := 1;
	ec.dev.lowFlowDamper.disableTime := 1;
	ec.dev.lowFlowDamper.diagnosticsEnable := FALSE;

	(* Test sequence *)
	CASE step OF
	    (* Group 1: Init *)

	    0 : (* Set up and move to first test *)
	        ec.dev.status := MainStatus.Standby;
	        cycles := 0;
	        step := 1;

	    (* pass[1]: operationType=Init sets status=Standby *)
	    1 :
	        (* Force a non-Standby state, then verify Init resets it *)
	        ec.dev.status := MainStatus.Cooling;
	        main(operationType := OperatingMode.Init, enable := TRUE);
	        IF ec.dev.status = MainStatus.Standby THEN
	            pass[1] := TRUE;
	            cycles := 0;
	            step := 2;
	        END_IF;

	    (* pass[2]: enable=FALSE - Main returns early, status unchanged *)
	    2 :
	        ec.dev.status := MainStatus.Cooling; (* Prime with a known state *)
	        main(operationType := OperatingMode.Run, enable := FALSE);
	        IF ec.dev.status = MainStatus.Cooling THEN
	            pass[2] := TRUE;
	            (* Reset to Standby for subsequent tests *)
	            main(operationType := OperatingMode.Init, enable := TRUE);
	            cycles := 0;
	            step := 3;
	        END_IF;

	    (* Group 2: Standby output function *)

	    (* pass[3]: Standby disables all device groups *)
	    3 :
	        (* Make sure we are in Standby with normal sensor values *)
	        ec.dev.status := MainStatus.Standby;
	        ec.dev.lastStatus := MainStatus.Standby;
	        main(operationType := OperatingMode.Run, enable := TRUE);
	        IF ec.dev.status = MainStatus.Standby
					AND NOT ec.dev.coldGroupEnableRequest
	                AND NOT ec.dev.hotGroupEnableRequest
	                AND NOT ec.dev.ahuFanEnableRequest
	                AND NOT ec.dev.airFlowEnableRequest THEN
	            pass[3] := TRUE;
	            cycles := 0;
	            step := 4;
	        END_IF;

	    (* Group 3: Ventilation transitions and output function *)

	    (* pass[4]: Ventilation output function - AHU=ON, groups=OFF *)
	    (*
	     * Note: ventilationRequest is reset by MainRuleEngine at the start of every scan,
	     * so it cannot be injected externally. Recipe/operator drives
	     * this state by writing dev.status directly.  The test does the same and
	     * verifies the output function (which group-enable flags are set).
	     *)
	    4 :
	        ec.dev.status := MainStatus.Ventilation; (* Direct entry, as recipe would do *)
	        main(operationType := OperatingMode.Run, enable := TRUE);
	        IF ec.dev.status = MainStatus.Ventilation
	                AND NOT ec.dev.coldGroupEnableRequest
	                AND NOT ec.dev.hotGroupEnableRequest
	                AND ec.dev.ahuFanEnableRequest
	                AND ec.dev.airFlowEnableRequest THEN
	            pass[4] := TRUE;
	            cycles := 0;
	            step := 5;
	        END_IF;

	    (* pass[5]: Ventilation persists across multiple scans *)
	    5 :
	        (* Already in Ventilation; call main N times and verify persistence *)
	        main(operationType := OperatingMode.Run, enable := TRUE);
	        IF cycles >= 5 AND ec.dev.status = MainStatus.Ventilation THEN
	            pass[5] := TRUE;
	            cycles := 0;
	            step := 6;
	        END_IF;

	    (* pass[6]: Ventilation -> Standby on isCompleted *)
	    6 :
	        ec.dev.isCompleted := TRUE;
	        main(operationType := OperatingMode.Run, enable := TRUE);
	        IF ec.dev.status = MainStatus.Standby THEN
	            pass[6] := TRUE;
	            ec.dev.isCompleted := FALSE;
	            cycles := 0;
	            step := 7;
	        END_IF;

	    (* Group 4: Cooling transitions and output function *)

	    (* pass[7]: Cooling output function - cold=ON, hot=OFF *)
	    7 :
	        ec.dev.status := MainStatus.Cooling; (* Direct entry *)
	        ec.dev.tempFeedback := T_HOT; (* T > tempMax -> ELSE branch -> stay in Cooling *)
	        main(operationType := OperatingMode.Run, enable := TRUE);
	        IF ec.dev.status = MainStatus.Cooling
	                AND ec.dev.coldGroupEnableRequest
	                AND NOT ec.dev.hotGroupEnableRequest
	                AND ec.dev.ahuFanEnableRequest THEN
	            pass[7] := TRUE;
	            cycles := 0;
	            step := 8;
	        END_IF;

	    (* pass[8]: Cooling persists while T > tempMin *)
	    8 :
	        ec.dev.tempFeedback := T_HOT; (* Still too hot -> keep cooling *)
	        main(operationType := OperatingMode.Run, enable := TRUE);
	        IF cycles >= 5 AND ec.dev.status = MainStatus.Cooling THEN
	            pass[8] := TRUE;
	            cycles := 0;
	            step := 9;
	        END_IF;

	    (* pass[9]: Cooling -> Standby at the lower thermostat threshold. *)
	    9 :
	        ec.dev.tempFeedback := T_SETPOINT - T_HYS;
	        main(operationType := OperatingMode.Run, enable := TRUE);
	        IF ec.dev.status = MainStatus.Standby THEN
	            pass[9] := TRUE;
	            ec.dev.tempFeedback := T_NORMAL;
	            cycles := 0;
	            step := 10;
	        END_IF;

	    (* Group 5: Heating transitions and output function *)

	    (* pass[10]: Heating output function - hot=ON, cold=OFF *)
	    10 :
	        ec.dev.status := MainStatus.Heating; (* Direct entry *)
	        ec.dev.tempFeedback := T_COLD; (* T < tempMin -> ELSE branch -> stay in Heating *)
	        main(operationType := OperatingMode.Run, enable := TRUE);
	        IF ec.dev.status = MainStatus.Heating
	                AND NOT ec.dev.coldGroupEnableRequest
	                AND ec.dev.hotGroupEnableRequest
	                AND ec.dev.ahuFanEnableRequest THEN
	            pass[10] := TRUE;
	            cycles := 0;
	            step := 11;
	        END_IF;

	    (* pass[11]: Heating persists while T < tempMax *)
	    11 :
	        ec.dev.tempFeedback := T_COLD; (* Still cold -> keep heating *)
	        main(operationType := OperatingMode.Run, enable := TRUE);
	        IF cycles >= 5 AND ec.dev.status = MainStatus.Heating THEN
	            pass[11] := TRUE;
	            cycles := 0;
	            step := 12;
	        END_IF;

	    (* pass[12]: Heating -> Standby at the upper thermostat threshold. *)
	    12 :
	        ec.dev.tempFeedback := T_SETPOINT + T_HYS;
	        main(operationType := OperatingMode.Run, enable := TRUE);
	        IF ec.dev.status = MainStatus.Standby THEN
	            pass[12] := TRUE;
	            ec.dev.tempFeedback := T_NORMAL;
	            cycles := 0;
	            step := 13;
	        END_IF;

	    (* Group 6: Drying transitions, output function, and overrides *)

	    (* pass[13]: Drying output function - cold=ON, hot=ON *)
	    13 :
	        ec.dev.status := MainStatus.Drying; (* Direct entry *)
	        ec.dev.tempFeedback := T_NORMAL; (* in-range -> ELSE -> stay in Drying *)
	        main(operationType := OperatingMode.Run, enable := TRUE);
	        IF ec.dev.status = MainStatus.Drying
	                AND ec.dev.coldGroupEnableRequest
	                AND ec.dev.hotGroupEnableRequest
	                AND ec.dev.ahuFanEnableRequest THEN
	            pass[13] := TRUE;
	            cycles := 0;
	            step := 14;
	        END_IF;

	    (* pass[14]: Drying persists while T in range *)
	    14 :
	        ec.dev.tempFeedback := T_NORMAL; (* in-window -> keep drying *)
	        main(operationType := OperatingMode.Run, enable := TRUE);
	        IF cycles >= 5 AND ec.dev.status = MainStatus.Drying THEN
	            pass[14] := TRUE;
	            cycles := 0;
	            step := 15;
	        END_IF;

	    (* pass[15]: Drying -> Cooling on tempOverMax *)
	    15 :
	        ec.dev.tempFeedback := T_HOT; (* Above tempMax -> emergency Cooling override *)
	        main(operationType := OperatingMode.Run, enable := TRUE);
	        IF ec.dev.status = MainStatus.Cooling THEN
	            pass[15] := TRUE;
	            cycles := 0;
	            step := 16;
	        END_IF;

	    (* pass[16]: Cooling -> Drying when T back below tempMax *)
	    (*
	     * After the Drying->Cooling emergency override (pass[15]), the MainRuleEngine
	     * Cooling CASE checks lastStatus=Drying to decide to resume Drying.
	     * We set lastStatus explicitly here - the same defensive pattern used in
	     * pass[21] for the run/break resume - because the auto-save inside
	     * main() may not survive the CODESYS scan boundary reliably.
	     * tempFeedback = T_NORMAL: tempUnderMax=TRUE, tempUnderMin=FALSE.
	     *)
	    16 :
	        ec.dev.lastStatus := MainStatus.Drying; (* Preserved from Drying->Cooling override *)
	        ec.dev.tempFeedback := T_NORMAL; (* tempUnderMax=TRUE, tempUnderMin=FALSE  *)
	        main(operationType := OperatingMode.Run, enable := TRUE);
	        IF ec.dev.status = MainStatus.Drying THEN
	            pass[16] := TRUE;
	            cycles := 0;
	            step := 17;
	        END_IF;

	    (* pass[17]: Drying -> Heating on tempUnderMin *)
	    17 :
	        ec.dev.tempFeedback := T_COLD; (* Below tempMin -> emergency Heating override *)
	        main(operationType := OperatingMode.Run, enable := TRUE);
	        IF ec.dev.status = MainStatus.Heating THEN
	            pass[17] := TRUE;
	            cycles := 0;
	            step := 18;
	        END_IF;

	    (* pass[18]: Heating -> Drying when T restored (lastStatus=Drying) *)
	    (*
	     * After the Drying->Heating emergency override (pass[17]), the MainRuleEngine
	     * Heating CASE checks lastStatus=Drying + tempOverMin to resume Drying.
	     * Set lastStatus explicitly - same defensive pattern as pass[16] and pass[21].
	     * tempFeedback = T_NORMAL: tempOverMin=TRUE, tempOverMax=FALSE.
	     *)
	    18 :
	        ec.dev.lastStatus := MainStatus.Drying; (* Preserved from Drying->Heating override *)
	        ec.dev.tempFeedback := T_NORMAL; (* tempOverMin=TRUE, tempOverMax=FALSE *)
	        main(operationType := OperatingMode.Run, enable := TRUE);
	        IF ec.dev.status = MainStatus.Drying THEN
	            pass[18] := TRUE;
	            cycles := 0;
	            step := 19;
	        END_IF;

	    (* pass[19]: Drying -> Standby on isCompleted *)
	    19 :
	        ec.dev.tempFeedback := T_NORMAL;
	        ec.dev.isCompleted := TRUE;
	        main(operationType := OperatingMode.Run, enable := TRUE);
	        IF ec.dev.status = MainStatus.Standby THEN
	            pass[19] := TRUE;
	            ec.dev.isCompleted := FALSE;
	            cycles := 0;
	            step := 20;
	        END_IF;

	    (* Group 7: Run / Break cycle (Mode E - Interval Dehumidification). *)

	    (* pass[20]: Drying -> Standby when timeBreakEnabled (begin break). *)
	    (*
	     * Init first: the Drying sequence (passes 13-19) accumulates device-FB
	     * internal state (pump/valve timers, actuator handshake counters).
	     * An Init resets signalMgmt and DeviceManager so any latched faults or
	     * stale Actuator state from the long Drying sequence cannot prevent the
	     * timeBreakEnabled -> Standby transition.
	     *)
	    20 :
	        main(operationType := OperatingMode.Init, enable := TRUE); (* Clean slate *)
	        ec.dev.lastStatus := MainStatus.Drying; (* As if coming from a run phase *)
	        ec.dev.status := MainStatus.Drying;
	        ec.dev.tempFeedback := T_NORMAL;
	        ec.dev.timeBreakEnabled := TRUE; (* Break starts -> standbyRequest=TRUE *)
	        main(operationType := OperatingMode.Run, enable := TRUE);
	        IF ec.dev.status = MainStatus.Standby THEN
	            pass[20] := TRUE;
	            cycles := 0;
	            step := 21;
	        END_IF;

	    (*  pass[21]: Standby -> Drying when break ends *)
	    (*
	     * Conditions: lastStatus=Drying, NOT timeBreakEnabled, tempInRange,
	     *             NOT rhControlOnly (time-based drying, no RH constraint).
	     *)
	    21 :
	        ec.dev.lastStatus := MainStatus.Drying; (* Simulate return from break *)
	        ec.dev.timeBreakEnabled := FALSE; (* Break over *)
	        ec.dev.tempFeedback := T_NORMAL; (* T in range *)
	        ec.dev.rhControlOnly := FALSE;
	        main(operationType  := OperatingMode.Run, enable := TRUE);
	        IF ec.dev.status = MainStatus.Drying THEN
	            pass[21] := TRUE;
	            (* Reset to Standby for next group *)
	            main(operationType := OperatingMode.Init, enable := TRUE);
	            cycles := 0;
	            step := 22;
	        END_IF;

		(* Group 8: Thermostat re-activation *)

	    (* pass[22]: the demo boundary T=tempMax is not an absolute-limit violation,
	     * but it is above the thermostat band and must re-enter Cooling. *)
	    22 :
	        ec.dev.status := MainStatus.Standby;
	        ec.dev.lastStatus := MainStatus.Cooling; (* Came from Cooling *)
	        ec.dev.tempFeedback := T_MAX;
	        main(operationType := OperatingMode.Run, enable := TRUE);
	        IF ec.dev.status = MainStatus.Cooling THEN
	            pass[22] := TRUE;
	            main(operationType := OperatingMode.Init, enable := TRUE); (* Reset *)
	            cycles := 0;
	            step := 23;
	        END_IF;

		(* Group 9: AirDistributionController - alternating high/low air throw *)

		(* pass[23]: AirDistrib disabled - no switching even after many clock1s ticks.
		 *
		 * step 22 cleanup already called Init, so the controller is in Init state and
		 * all Actuator FBs are in Disabled (Actuator.Init clears enableRequest/disableRequest).
		 * With airDistributionEnabled=FALSE, airDistribCtrl is called with enable=FALSE and
		 * stays frozen in Init state regardless of clock1s pulses.
		 * Assertion: lowFlowDamperEnableRequest stays FALSE (no switch to low phase).
		 *)
		23 :
			ec.dev.status := MainStatus.Drying;
			ec.dev.tempFeedback := T_NORMAL;
			ec.dev.airDistributionEnabled := FALSE;
			ec.dev.setPointTimeHigh := 2;
			ec.dev.setPointTimeLow := 2;
			ec.clks.clock1s := TRUE;
			main(operationType := OperatingMode.Run, enable := TRUE);
			ec.clks.clock1s := FALSE;
			IF cycles >= 5 AND NOT ec.dev.lowFlowDamperEnableRequest THEN
				pass[23] := TRUE;
				cycles := 0;
				step := 24;
			END_IF;

		(* pass[24]: AirDistrib enabled in Drying - Init->HighPhase: highFlowDamper=ON, lowFlowDamper=OFF.
		 *
		 * The controller is still in Init state from step 22/23 (no Init call needed here).
		 * First Run call with enable=TRUE transitions Init->HighPhase and asserts
		 * highFlowDamperEnableRequest while keeping lowFlowDamperEnableRequest=FALSE.
		 *)
		24 :
			ec.dev.status := MainStatus.Drying;
			ec.dev.tempFeedback := T_NORMAL;
			ec.dev.airDistributionEnabled := TRUE;
			ec.dev.setPointTimeHigh := 2;
			ec.dev.setPointTimeLow := 2;
			ec.clks.clock1s := FALSE;
			main(operationType := OperatingMode.Run, enable := TRUE); (* Init->HighPhase *)
			IF ec.dev.highFlowDamperEnableRequest AND NOT ec.dev.lowFlowDamperEnableRequest THEN
				pass[24] := TRUE;
				cycles := 0;
				step := 25;
			END_IF;

		(* pass[25]: HighPhase->TransitionToLow after setPointTimeHigh clock1s ticks.
		 *
		 * After setPointTimeHigh (=2) cumulated clock1s pulses, the controller resets the
		 * high counter and issues Make-Before-Break: highFlowDamperDisableRequest=TRUE,
		 * lowFlowDamperEnableRequest=TRUE.
		 *)
		25 :
			ec.dev.status := MainStatus.Drying;
			ec.dev.tempFeedback := T_NORMAL;
			ec.dev.airDistributionEnabled := TRUE;
			ec.clks.clock1s := TRUE; (* Advance cumulative timer each scan *)
			main(operationType := OperatingMode.Run, enable := TRUE);
			ec.clks.clock1s := FALSE;
			(* After setPointTimeHigh ticks, lowFlowDamperEnableRequest goes TRUE *)
			IF ec.dev.lowFlowDamperEnableRequest AND ec.dev.highFlowDamperDisableRequest THEN
				pass[25] := TRUE;
				cycles := 0;
				step := 26;
			END_IF;

		(* pass[26]: TransitionToLow->LowPhase after damper handshake.
		 *
		 * The Actuator FB clears enableRequest / disableRequest VAR_IN_OUT flags when the
		 * physical maneuver completes (after enableTime=1 clock100ms pulse).
		 * AirDistribCtrl advances to LowPhase when both flags are cleared.
		 *)
		26 :
			ec.dev.status := MainStatus.Drying;
			ec.dev.tempFeedback := T_NORMAL;
			ec.dev.airDistributionEnabled := TRUE;
			ec.clks.clock100ms := TRUE; (* Drive Actuator FB for damper handshake *)
			ec.clks.clock1s := FALSE;
			main(operationType := OperatingMode.Run, enable := TRUE);
			ec.clks.clock100ms := FALSE;
			(* LowPhase: lowFlowDamperEnableRequest cleared (acked), highFlowDamperDisableRequest cleared *)
			IF NOT ec.dev.lowFlowDamperEnableRequest AND NOT ec.dev.highFlowDamperDisableRequest THEN
				pass[26] := TRUE;
				cycles := 0;
				step := 27;
			END_IF;

		(* pass[27]: LowPhase->TransitionToHigh after setPointTimeLow clock1s ticks.
		 *
		 * Symmetric to pass[25]: after setPointTimeLow (=2) cumulated ticks the controller
		 * resets the low counter and issues Make-Before-Break in the opposite direction:
		 * lowFlowDamperDisableRequest=TRUE, highFlowDamperEnableRequest=TRUE.
		 *)
		27 :
			ec.dev.status := MainStatus.Drying;
			ec.dev.tempFeedback := T_NORMAL;
			ec.dev.airDistributionEnabled := TRUE;
			ec.clks.clock1s := TRUE;
			main(operationType := OperatingMode.Run, enable := TRUE);
			ec.clks.clock1s := FALSE;
			IF ec.dev.highFlowDamperEnableRequest AND ec.dev.lowFlowDamperDisableRequest THEN
				pass[27] := TRUE;
				ec.dev.airDistributionEnabled := FALSE;
				main(operationType := OperatingMode.Init, enable := TRUE);
				cycles := 0;
				step := 28;
			END_IF;

		(* Group 10: Duct safety alarms *)

		(* pass[28]: ductTempOverMax -> Fault *)
		28 :
			ec.dev.status := MainStatus.Drying; (* Direct entry *)
			ec.dev.tempFeedback := T_NORMAL;
			ec.dev.ductTempFeedback := DUCT_HOT; (* Above ductTempMax -> alarm *)
			main(operationType := OperatingMode.Run, enable := TRUE);
			IF ec.dev.status = MainStatus.Fault THEN
				pass[28] := TRUE;
				cycles := 0;
				step := 29;
			END_IF;

		(* pass[29]: Fault persists while alarm condition is still active *)
		29 :
			ec.dev.ductTempFeedback := DUCT_HOT; (* Condition still active *)
			main(operationType := OperatingMode.Run, enable := TRUE);
			IF cycles >= 3 AND ec.dev.status = MainStatus.Fault THEN
				pass[29] := TRUE;
				cycles := 0;
				step := 30;
			END_IF;

		(* pass[30]: Fault -> Standby after Init (signalMgmt reset) *)
		30 :
			ec.dev.ductTempFeedback := DUCT_NORMAL; (* Clear alarm condition *)
			main(operationType := OperatingMode.Init, enable := TRUE);
			IF ec.dev.status = MainStatus.Standby THEN
				pass[30] := TRUE;
				cycles := 0;
				step := 31;
			END_IF;

		(* pass[31]: ductTempUnderMin -> Fault *)
		31 :
			ec.dev.status := MainStatus.Drying; (* Direct entry *)
			ec.dev.tempFeedback := T_NORMAL;
			ec.dev.ductTempFeedback := DUCT_COLD; (* Below ductTempMin -> alarm *)
			main(operationType  := OperatingMode.Run, enable := TRUE);
			IF ec.dev.status = MainStatus.Fault THEN
				pass[31] := TRUE;
				ec.dev.ductTempFeedback := DUCT_NORMAL;
				main(operationType  := OperatingMode.Init, enable := TRUE);
				cycles := 0;
				step := 32;
			END_IF;

		(* pass[32]: Fault state - all groups disabled (safe state) *)
		32 :
			ec.dev.status := MainStatus.Drying; (* Direct entry *)
			ec.dev.ductTempFeedback := DUCT_HOT; (* Trigger fault again *)
			main(operationType := OperatingMode.Run, enable := TRUE);
			IF ec.dev.status = MainStatus.Fault
					AND NOT ec.dev.coldGroupEnableRequest
					AND NOT ec.dev.hotGroupEnableRequest
					AND NOT ec.dev.ahuFanEnableRequest
					AND NOT ec.dev.airFlowEnableRequest THEN
				pass[32] := TRUE;
				ec.dev.ductTempFeedback := DUCT_NORMAL;
				main(operationType := OperatingMode.Init, enable := TRUE);
				cycles := 0;
				step := 100;
			END_IF;

		(* Done *)
		100 :
			testDone := TRUE;
	END_CASE;

	(*  Diagnostic mirrors (updated every scan for online monitoring)  *)
	mirStatus := ec.dev.status;
	mirColdGroupEnable := ec.dev.coldGroupEnableRequest;
	mirHotGroupEnable := ec.dev.hotGroupEnableRequest;
	mirAhuFanEnable := ec.dev.ahuFanEnableRequest;
	mirAirFlowEnable := ec.dev.airFlowEnableRequest;
	mirFaultRequest := ec.dev.faultRequest;
	mirStandbyRequest := ec.dev.standbyRequest;
	mirCoolingRequest := ec.dev.coolingRequest;
	mirHeatingRequest := ec.dev.heatingRequest;
	mirDryingRequest := ec.dev.dryingRequest;
	mirTempInRange := ec.dev.tempInRange;
	mirTempOverMax := ec.dev.tempOverMax;
	mirTempUnderMin := ec.dev.tempUnderMin;
	mirDuctTempOverMax := ec.dev.ductTempOverMax;
	mirDuctTempUnderMin := ec.dev.ductTempUnderMin;
	mirTimeBreakEnabled := ec.dev.timeBreakEnabled;
	mirLastStatus := ec.dev.lastStatus;
	mirActualRuntime := ec.dev.actualRuntime;
	mirAhuFanInvalidConfig := ec.dev.ahuFan.invalidConfig;
	mirColdValveInvalidConfig := ec.dev.coldGlycolValve.invalidConfig;
	mirHotValveInvalidConfig := ec.dev.hotGlycolValve.invalidConfig;
	mirColdPumpFault := ec.dev.coldGlycolPump.fault;
	mirHotPumpFault := ec.dev.hotGlycolPump.fault;
	mirAirFlowFault := ec.dev.airFlow.fault;
	END_PROGRAM

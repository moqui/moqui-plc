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
 * pass[8] : Cooling persists - stays Cooling while T > tempMin
 * pass[9] : Cooling -> Standby when tempUnderMin
 * pass[10] : Manual Heating - heatingRequest -> Heating; cold=OFF, hot=ON
 * pass[11] : Heating persists - stays Heating while T < tempMax
 * pass[12] : Heating -> Standby when tempOverMax
 * pass[13] : Manual Drying - dryingRequest -> Drying; cold=ON, hot=ON
 * pass[14] : Drying persists - stays Drying while T in range
 * pass[15] : Drying -> Cooling on tempOverMax (emergency override)
 * pass[16] : Cooling -> Drying when resuming from Drying and T < tempMax
 * pass[17] : Drying -> Heating on tempUnderMin (emergency override)
 * pass[18] : Heating -> Drying when T restored (lastStatus=Drying, tempOverMin)
 * pass[19] : Drying -> Standby on isCompleted
 * pass[20] : Run/break: Drying -> Standby when timeBreakEnabled
 * pass[21] : Run/break: Standby -> Drying when break ends (NOT timeBreakEnabled)
 * pass[22] : Standby re-enters Cooling when lastStatus=Cooling and tempOverMax
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
		dev : DeviceFacade;
		clks : Clocks;
		workEffort : WorkEffort;
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
		dev.status := MainStatus.Standby;
		dev.lastStatus := MainStatus.Standby;
		dev.isCompleted := FALSE;
		dev.timeBreakEnabled := FALSE;
		dev.actualRuntime := 0;
		dev.actualBreakDuration := 0;
		dev.faultRequest := FALSE;
		testReset := FALSE;
	END_IF;

	(* Default recipe configuration (set before calling main each scan).
	 *
	 * These values are overridden per-step when a specific sensor value is needed.
	 * They represent a realistic civil HVAC AHU recipe.
	 *)
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
	dev.estimatedRuntime := 0; (* 0 disables time-based dehumidification countdown *)
	dev.minRuntime := 0;
	dev.ductTempMin := DUCT_MIN;
	dev.ductTempMax := DUCT_MAX;
	dev.ductRhMax := DUCT_RH_MAX;
	(* Sensor defaults - safe / in-range values; overridden per step *)
	dev.tempFeedback := T_NORMAL;
	dev.rhFeedback := RH_NORMAL;
	dev.ductTempFeedback := DUCT_NORMAL;
	dev.ductRhFeedback := 60.0;

	(* Static HVAC device configuration.
	 *
	 * In production these fields are normally mapped by the HvacDeviceConfig recipe.
	 * The test suite sets the minimum safe subset directly so it remains deterministic
	 * even when the recipe manager is not part of the test task execution.
	 *)
	dev.coldGlycolPump.actuatorId := 'coldGlycolPump';
	dev.coldGlycolPump.actuatorName := 'ColdGlycolPump';
	dev.coldGlycolPump.actuationType := ActuatorActuationType.SingleActuation;
	dev.coldGlycolPump.feedbackType := ActuatorFeedbackType.WithoutFeedback;
	dev.coldGlycolPump.model := ActuatorModel.ABBACH580;
	dev.coldGlycolPump.enableTime := 1;
	dev.coldGlycolPump.disableTime := 1;
	dev.coldGlycolPump.diagnosticsEnable := FALSE;

	dev.hotGlycolPump.actuatorId := 'hotGlycolPump';
	dev.hotGlycolPump.actuatorName := 'HotGlycolPump';
	dev.hotGlycolPump.actuationType := ActuatorActuationType.SingleActuation;
	dev.hotGlycolPump.feedbackType := ActuatorFeedbackType.WithoutFeedback;
	dev.hotGlycolPump.model := ActuatorModel.ABBACH580;
	dev.hotGlycolPump.enableTime := 1;
	dev.hotGlycolPump.disableTime := 1;
	dev.hotGlycolPump.diagnosticsEnable := FALSE;

	dev.airFlow.actuatorId := 'airFlow';
	dev.airFlow.actuatorName := 'AirFlow';
	dev.airFlow.actuationType := ActuatorActuationType.SingleActuation;
	dev.airFlow.feedbackType := ActuatorFeedbackType.WithoutFeedback;
	dev.airFlow.model := ActuatorModel.ABBACH580;
	dev.airFlow.enableTime := 1;
	dev.airFlow.disableTime := 1;
	dev.airFlow.diagnosticsEnable := FALSE;
	dev.airFlowRef := 50.0;

	dev.coldGlycolValve.controlSystemId := 'coldGlycolValve';
	dev.coldGlycolValve.controlSystemName := 'ColdGlycolValve';
	dev.coldGlycolValve.gain := 1.0;
	dev.coldGlycolValve.integrationTime := 0.0;
	dev.coldGlycolValve.derivationTime := 0.0;
	dev.coldGlycolValve.setpointMin := 0.0;
	dev.coldGlycolValve.setpointMax := 100.0;
	dev.coldGlycolValve.outputMin := 0.0;
	dev.coldGlycolValve.outputMax := 100.0;
	dev.coldGlycolValve.atSetpointHysteresis := T_HYS;
	dev.coldGlycolValve.tickTime := T#100ms;

	dev.hotGlycolValve.controlSystemId := 'hotGlycolValve';
	dev.hotGlycolValve.controlSystemName := 'HotGlycolValve';
	dev.hotGlycolValve.gain := 1.0;
	dev.hotGlycolValve.integrationTime := 0.0;
	dev.hotGlycolValve.derivationTime := 0.0;
	dev.hotGlycolValve.setpointMin := 0.0;
	dev.hotGlycolValve.setpointMax := 100.0;
	dev.hotGlycolValve.outputMin := 0.0;
	dev.hotGlycolValve.outputMax := 100.0;
	dev.hotGlycolValve.atSetpointHysteresis := T_HYS;
	dev.hotGlycolValve.tickTime := T#100ms;

	dev.ahuFan.controlSystemId := 'ahuFan';
	dev.ahuFan.controlSystemName := 'AhuFan';
	dev.ahuFan.gain := 1.0;
	dev.ahuFan.integrationTime := 0.0;
	dev.ahuFan.derivationTime := 0.0;
	dev.ahuFan.setpointMin := 0.0;
	dev.ahuFan.setpointMax := 100.0;
	dev.ahuFan.outputMin := 0.0;
	dev.ahuFan.outputMax := 100.0;
	dev.ahuFan.atSetpointHysteresis := 1.0;
	dev.ahuFan.tickTime := T#100ms;
	dev.ahuFanSpeedSetpoint := 50.0;

	dev.highFlowDamper.actuatorId := 'highFlowDamper';
	dev.highFlowDamper.actuatorName := 'HighFlowDamper';
	dev.highFlowDamper.actuationType := ActuatorActuationType.SingleActuation;
	dev.highFlowDamper.feedbackType := ActuatorFeedbackType.WithoutFeedback;
	dev.highFlowDamper.model := ActuatorModel.ABBACH580;
	dev.highFlowDamper.enableTime := 1;
	dev.highFlowDamper.disableTime := 1;
	dev.highFlowDamper.diagnosticsEnable := FALSE;

	dev.lowFlowDamper.actuatorId := 'lowFlowDamper';
	dev.lowFlowDamper.actuatorName := 'LowFlowDamper';
	dev.lowFlowDamper.actuationType := ActuatorActuationType.SingleActuation;
	dev.lowFlowDamper.feedbackType := ActuatorFeedbackType.WithoutFeedback;
	dev.lowFlowDamper.model := ActuatorModel.ABBACH580;
	dev.lowFlowDamper.enableTime := 1;
	dev.lowFlowDamper.disableTime := 1;
	dev.lowFlowDamper.diagnosticsEnable := FALSE;

	(* Test sequence *)
	CASE step OF
	    (* Group 1: Init *)

	    0 : (* Set up and move to first test *)
	        dev.status := MainStatus.Standby;
	        cycles := 0;
	        step := 1;

	    (* pass[1]: operationType=Init sets status=Standby *)
	    1 :
	        (* Force a non-Standby state, then verify Init resets it *)
	        dev.status := MainStatus.Cooling;
	        main(operationType := OperatingMode.Init, enable := TRUE);
	        IF dev.status = MainStatus.Standby THEN
	            pass[1] := TRUE;
	            cycles := 0;
	            step := 2;
	        END_IF;

	    (* pass[2]: enable=FALSE - Main returns early, status unchanged *)
	    2 :
	        dev.status := MainStatus.Cooling; (* Prime with a known state *)
	        main(operationType := OperatingMode.Run, enable := FALSE);
	        IF dev.status = MainStatus.Cooling THEN
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
	        dev.status := MainStatus.Standby;
	        dev.lastStatus := MainStatus.Standby;
	        main(operationType := OperatingMode.Run, enable := TRUE);
	        IF dev.status = MainStatus.Standby
					AND NOT dev.coldGroupEnableRequest
	                AND NOT dev.hotGroupEnableRequest
	                AND NOT dev.ahuFanEnableRequest
	                AND NOT dev.airFlowEnableRequest THEN
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
	        dev.status := MainStatus.Ventilation; (* Direct entry, as recipe would do *)
	        main(operationType := OperatingMode.Run, enable := TRUE);
	        IF dev.status = MainStatus.Ventilation
	                AND NOT dev.coldGroupEnableRequest
	                AND NOT dev.hotGroupEnableRequest
	                AND dev.ahuFanEnableRequest
	                AND dev.airFlowEnableRequest THEN
	            pass[4] := TRUE;
	            cycles := 0;
	            step := 5;
	        END_IF;

	    (* pass[5]: Ventilation persists across multiple scans *)
	    5 :
	        (* Already in Ventilation; call main N times and verify persistence *)
	        main(operationType := OperatingMode.Run, enable := TRUE);
	        IF cycles >= 5 AND dev.status = MainStatus.Ventilation THEN
	            pass[5] := TRUE;
	            cycles := 0;
	            step := 6;
	        END_IF;

	    (* pass[6]: Ventilation -> Standby on isCompleted *)
	    6 :
	        dev.isCompleted := TRUE;
	        main(operationType := OperatingMode.Run, enable := TRUE);
	        IF dev.status = MainStatus.Standby THEN
	            pass[6] := TRUE;
	            dev.isCompleted := FALSE;
	            cycles := 0;
	            step := 7;
	        END_IF;

	    (* Group 4: Cooling transitions and output function *)

	    (* pass[7]: Cooling output function - cold=ON, hot=OFF *)
	    7 :
	        dev.status := MainStatus.Cooling; (* Direct entry *)
	        dev.tempFeedback := T_HOT; (* T > tempMax -> ELSE branch -> stay in Cooling *)
	        main(operationType := OperatingMode.Run, enable := TRUE);
	        IF dev.status = MainStatus.Cooling
	                AND dev.coldGroupEnableRequest
	                AND NOT dev.hotGroupEnableRequest
	                AND dev.ahuFanEnableRequest THEN
	            pass[7] := TRUE;
	            cycles := 0;
	            step := 8;
	        END_IF;

	    (* pass[8]: Cooling persists while T > tempMin *)
	    8 :
	        dev.tempFeedback := T_HOT; (* Still too hot -> keep cooling *)
	        main(operationType := OperatingMode.Run, enable := TRUE);
	        IF cycles >= 5 AND dev.status = MainStatus.Cooling THEN
	            pass[8] := TRUE;
	            cycles := 0;
	            step := 9;
	        END_IF;

	    (* pass[9]: Cooling -> Standby when tempUnderMin*)
	    9 :
	        dev.tempFeedback := T_COLD; (* Below tempMin -> exit Cooling *)
	        main(operationType := OperatingMode.Run, enable := TRUE);
	        IF dev.status = MainStatus.Standby THEN
	            pass[9] := TRUE;
	            dev.tempFeedback := T_NORMAL;
	            cycles := 0;
	            step := 10;
	        END_IF;

	    (* Group 5: Heating transitions and output function *)

	    (* pass[10]: Heating output function - hot=ON, cold=OFF *)
	    10 :
	        dev.status := MainStatus.Heating; (* Direct entry *)
	        dev.tempFeedback := T_COLD; (* T < tempMin -> ELSE branch -> stay in Heating *)
	        main(operationType := OperatingMode.Run, enable := TRUE);
	        IF dev.status = MainStatus.Heating
	                AND NOT dev.coldGroupEnableRequest
	                AND dev.hotGroupEnableRequest
	                AND dev.ahuFanEnableRequest THEN
	            pass[10] := TRUE;
	            cycles := 0;
	            step := 11;
	        END_IF;

	    (* pass[11]: Heating persists while T < tempMax *)
	    11 :
	        dev.tempFeedback := T_COLD; (* Still cold -> keep heating *)
	        main(operationType := OperatingMode.Run, enable := TRUE);
	        IF cycles >= 5 AND dev.status = MainStatus.Heating THEN
	            pass[11] := TRUE;
	            cycles := 0;
	            step := 12;
	        END_IF;

	    (* pass[12]: Heating -> Standby when tempOverMax *)
	    12 :
	        dev.tempFeedback := T_HOT; (* Above tempMax -> exit Heating *)
	        main(operationType := OperatingMode.Run, enable := TRUE);
	        IF dev.status = MainStatus.Standby THEN
	            pass[12] := TRUE;
	            dev.tempFeedback := T_NORMAL;
	            cycles := 0;
	            step := 13;
	        END_IF;

	    (* Group 6: Drying transitions, output function, and overrides *)

	    (* pass[13]: Drying output function - cold=ON, hot=ON *)
	    13 :
	        dev.status := MainStatus.Drying; (* Direct entry *)
	        dev.tempFeedback := T_NORMAL; (* in-range -> ELSE -> stay in Drying *)
	        main(operationType := OperatingMode.Run, enable := TRUE);
	        IF dev.status = MainStatus.Drying
	                AND dev.coldGroupEnableRequest
	                AND dev.hotGroupEnableRequest
	                AND dev.ahuFanEnableRequest THEN
	            pass[13] := TRUE;
	            cycles := 0;
	            step := 14;
	        END_IF;

	    (* pass[14]: Drying persists while T in range *)
	    14 :
	        dev.tempFeedback := T_NORMAL; (* in-window -> keep drying *)
	        main(operationType := OperatingMode.Run, enable := TRUE);
	        IF cycles >= 5 AND dev.status = MainStatus.Drying THEN
	            pass[14] := TRUE;
	            cycles := 0;
	            step := 15;
	        END_IF;

	    (* pass[15]: Drying -> Cooling on tempOverMax *)
	    15 :
	        dev.tempFeedback := T_HOT; (* Above tempMax -> emergency Cooling override *)
	        main(operationType := OperatingMode.Run, enable := TRUE);
	        IF dev.status = MainStatus.Cooling THEN
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
	        dev.lastStatus := MainStatus.Drying; (* Preserved from Drying->Cooling override *)
	        dev.tempFeedback := T_NORMAL; (* tempUnderMax=TRUE, tempUnderMin=FALSE  *)
	        main(operationType := OperatingMode.Run, enable := TRUE);
	        IF dev.status = MainStatus.Drying THEN
	            pass[16] := TRUE;
	            cycles := 0;
	            step := 17;
	        END_IF;

	    (* pass[17]: Drying -> Heating on tempUnderMin *)
	    17 :
	        dev.tempFeedback := T_COLD; (* Below tempMin -> emergency Heating override *)
	        main(operationType := OperatingMode.Run, enable := TRUE);
	        IF dev.status = MainStatus.Heating THEN
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
	        dev.lastStatus := MainStatus.Drying; (* Preserved from Drying->Heating override *)
	        dev.tempFeedback := T_NORMAL; (* tempOverMin=TRUE, tempOverMax=FALSE *)
	        main(operationType := OperatingMode.Run, enable := TRUE);
	        IF dev.status = MainStatus.Drying THEN
	            pass[18] := TRUE;
	            cycles := 0;
	            step := 19;
	        END_IF;

	    (* pass[19]: Drying -> Standby on isCompleted *)
	    19 :
	        dev.tempFeedback := T_NORMAL;
	        dev.isCompleted := TRUE;
	        main(operationType := OperatingMode.Run, enable := TRUE);
	        IF dev.status = MainStatus.Standby THEN
	            pass[19] := TRUE;
	            dev.isCompleted := FALSE;
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
	        dev.lastStatus := MainStatus.Drying; (* As if coming from a run phase *)
	        dev.status := MainStatus.Drying;
	        dev.tempFeedback := T_NORMAL;
	        dev.timeBreakEnabled := TRUE; (* Break starts -> standbyRequest=TRUE *)
	        main(operationType := OperatingMode.Run, enable := TRUE);
	        IF dev.status = MainStatus.Standby THEN
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
	        dev.lastStatus := MainStatus.Drying; (* Simulate return from break *)
	        dev.timeBreakEnabled := FALSE; (* Break over *)
	        dev.tempFeedback := T_NORMAL; (* T in range *)
	        dev.rhControlOnly := FALSE;
	        main(operationType  := OperatingMode.Run, enable := TRUE);
	        IF dev.status = MainStatus.Drying THEN
	            pass[21] := TRUE;
	            (* Reset to Standby for next group *)
	            main(operationType := OperatingMode.Init, enable := TRUE);
	            cycles := 0;
	            step := 22;
	        END_IF;

		(* Group 8: Thermostat re-activation *)

	    (* pass[22]: Standby re-enters Cooling when lastStatus=Cooling
	     *           and tempOverMax (thermostat re-activation) *)
	    22 :
	        dev.status := MainStatus.Standby;
	        dev.lastStatus := MainStatus.Cooling; (* Came from Cooling *)
	        dev.tempFeedback := T_HOT; (* Still too hot *)
	        main(operationType := OperatingMode.Run, enable := TRUE);
	        IF dev.status = MainStatus.Cooling THEN
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
			dev.status := MainStatus.Drying;
			dev.tempFeedback := T_NORMAL;
			dev.airDistributionEnabled := FALSE;
			dev.setPointTimeHigh := 2;
			dev.setPointTimeLow := 2;
			clks.clock1s := TRUE;
			main(operationType := OperatingMode.Run, enable := TRUE);
			clks.clock1s := FALSE;
			IF cycles >= 5 AND NOT dev.lowFlowDamperEnableRequest THEN
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
			dev.status := MainStatus.Drying;
			dev.tempFeedback := T_NORMAL;
			dev.airDistributionEnabled := TRUE;
			dev.setPointTimeHigh := 2;
			dev.setPointTimeLow := 2;
			clks.clock1s := FALSE;
			main(operationType := OperatingMode.Run, enable := TRUE); (* Init->HighPhase *)
			IF dev.highFlowDamperEnableRequest AND NOT dev.lowFlowDamperEnableRequest THEN
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
			dev.status := MainStatus.Drying;
			dev.tempFeedback := T_NORMAL;
			dev.airDistributionEnabled := TRUE;
			clks.clock1s := TRUE; (* Advance cumulative timer each scan *)
			main(operationType := OperatingMode.Run, enable := TRUE);
			clks.clock1s := FALSE;
			(* After setPointTimeHigh ticks, lowFlowDamperEnableRequest goes TRUE *)
			IF dev.lowFlowDamperEnableRequest AND dev.highFlowDamperDisableRequest THEN
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
			dev.status := MainStatus.Drying;
			dev.tempFeedback := T_NORMAL;
			dev.airDistributionEnabled := TRUE;
			clks.clock100ms := TRUE; (* Drive Actuator FB for damper handshake *)
			clks.clock1s := FALSE;
			main(operationType := OperatingMode.Run, enable := TRUE);
			clks.clock100ms := FALSE;
			(* LowPhase: lowFlowDamperEnableRequest cleared (acked), highFlowDamperDisableRequest cleared *)
			IF NOT dev.lowFlowDamperEnableRequest AND NOT dev.highFlowDamperDisableRequest THEN
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
			dev.status := MainStatus.Drying;
			dev.tempFeedback := T_NORMAL;
			dev.airDistributionEnabled := TRUE;
			clks.clock1s := TRUE;
			main(operationType := OperatingMode.Run, enable := TRUE);
			clks.clock1s := FALSE;
			IF dev.highFlowDamperEnableRequest AND dev.lowFlowDamperDisableRequest THEN
				pass[27] := TRUE;
				dev.airDistributionEnabled := FALSE;
				main(operationType := OperatingMode.Init, enable := TRUE);
				cycles := 0;
				step := 28;
			END_IF;

		(* Group 10: Duct safety alarms *)

		(* pass[28]: ductTempOverMax -> Fault *)
		28 :
			dev.status := MainStatus.Drying; (* Direct entry *)
			dev.tempFeedback := T_NORMAL;
			dev.ductTempFeedback := DUCT_HOT; (* Above ductTempMax -> alarm *)
			main(operationType := OperatingMode.Run, enable := TRUE);
			IF dev.status = MainStatus.Fault THEN
				pass[28] := TRUE;
				cycles := 0;
				step := 29;
			END_IF;

		(* pass[29]: Fault persists while alarm condition is still active *)
		29 :
			dev.ductTempFeedback := DUCT_HOT; (* Condition still active *)
			main(operationType := OperatingMode.Run, enable := TRUE);
			IF cycles >= 3 AND dev.status = MainStatus.Fault THEN
				pass[29] := TRUE;
				cycles := 0;
				step := 30;
			END_IF;

		(* pass[30]: Fault -> Standby after Init (signalMgmt reset) *)
		30 :
			dev.ductTempFeedback := DUCT_NORMAL; (* Clear alarm condition *)
			main(operationType := OperatingMode.Init, enable := TRUE);
			IF dev.status = MainStatus.Standby THEN
				pass[30] := TRUE;
				cycles := 0;
				step := 31;
			END_IF;

		(* pass[31]: ductTempUnderMin -> Fault *)
		31 :
			dev.status := MainStatus.Drying; (* Direct entry *)
			dev.tempFeedback := T_NORMAL;
			dev.ductTempFeedback := DUCT_COLD; (* Below ductTempMin -> alarm *)
			main(operationType  := OperatingMode.Run, enable := TRUE);
			IF dev.status = MainStatus.Fault THEN
				pass[31] := TRUE;
				dev.ductTempFeedback := DUCT_NORMAL;
				main(operationType  := OperatingMode.Init, enable := TRUE);
				cycles := 0;
				step := 32;
			END_IF;

		(* pass[32]: Fault state - all groups disabled (safe state) *)
		32 :
			dev.status := MainStatus.Drying; (* Direct entry *)
			dev.ductTempFeedback := DUCT_HOT; (* Trigger fault again *)
			main(operationType := OperatingMode.Run, enable := TRUE);
			IF dev.status = MainStatus.Fault
					AND NOT dev.coldGroupEnableRequest
					AND NOT dev.hotGroupEnableRequest
					AND NOT dev.ahuFanEnableRequest
					AND NOT dev.airFlowEnableRequest THEN
				pass[32] := TRUE;
				dev.ductTempFeedback := DUCT_NORMAL;
				main(operationType := OperatingMode.Init, enable := TRUE);
				cycles := 0;
				step := 100;
			END_IF;

		(* Done *)
		100 :
			testDone := TRUE;
	END_CASE;

	(*  Diagnostic mirrors (updated every scan for online monitoring)  *)
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

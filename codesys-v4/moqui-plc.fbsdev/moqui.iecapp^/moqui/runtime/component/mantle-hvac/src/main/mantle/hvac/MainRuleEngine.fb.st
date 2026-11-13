(*
 * MainRuleEngine - transition-condition logic for the HVAC supervisor FSM.
 *
 * Responsibilities:
 *   1. Reset transition requests to safe defaults.
 *   2. Run the signal management engine (fault / alarm / warning detection).
 *   3. Compute boolean predicates from sensor feedback and recipe setpoints.
 *   4. Implement the per-state transition-condition rules.
 *
 * Default / persistence convention
 * At the top of every scan standbyRequest is set TRUE (safe default).
 * Each ACTIVE-state CASE block MUST:
 *   - Set standbyRequest := FALSE (keep current state) in the ELSE branch.
 *   - Set standbyRequest := TRUE (or leave as-is) when an EXIT condition is met.
 *   - Set standbyRequest := FALSE and another*Request := TRUE to switch phase.
 *
 * Without the ELSE branch the system would exit any active state to Standby
 * on the very first scan - a single-scan flash rather than a persistent phase.
 *
 * Operating modes:
 *   Mode A Thermostat Cooling -> Cooling
 *   Mode B Cooling with RH% dehumidification -> Cooling (rhControlEnabled)
 *   Mode C Winter Heating -> Heating
 *   Mode D Heating with RH% control -> Heating (rhControlEnabled)
 *   Mode E Interval Dehumidification (on/off) -> Drying <-> Standby (break)
 *   Mode F Dehumidification by RH% target -> Drying (rhControlEnabled)
 *
 * Duct safety (duct sensors):
 *   The duct T+RH sensor monitors supply-air conditions upstream of the zone.
 *   Limit violations raise alarms to protect equipment and occupants.
 *   ductTempOverMax -> supply air too hot -> ImmediateStop
 *   ductTempUnderMin -> supply air too cold -> ImmediateStop
 *   ductRhOverMax -> supply air saturated -> Warning only (condensation risk)
 *)
FUNCTION_BLOCK MainRuleEngine
	
	VAR_INPUT
		operationType : OperatingMode := OperatingMode.Run;
	END_VAR
	VAR_OUTPUT
		error : BOOL;
	END_VAR
	VAR
		(* Device diagnostics *)
		deviceDiags : DeviceDiagnostics;
	END_VAR

	(* Reset transition requests to safe defaults.
	 *
	 * standbyRequest = TRUE -> return to / stay in Standby (safe default).
	 * Active-state CASE blocks override to FALSE to keep the current phase alive,
	 * or set another *Request to switch phases.
	 *)
	ec.dev.faultRequest := FALSE;
	ec.dev.standbyRequest := TRUE;
	ec.dev.heatingRequest := FALSE;
	ec.dev.coolingRequest := FALSE;
	ec.dev.ventilationRequest := FALSE;
	ec.dev.dryingRequest := FALSE;

	deviceDiags(operationType := operationType, error => error);

	(* Compute sensor predicates *)

	(* Process temperature sensor *)
	ec.dev.tempInRange := (ec.dev.tempFeedback >= ec.dev.tempMin + ec.dev.tempHysteresis)
		AND (ec.dev.tempFeedback <= ec.dev.tempMax - ec.dev.tempHysteresis);
	ec.dev.tempAtSetpoint := ABS(ec.dev.tempFeedback - ec.dev.tempSetpoint) <= ec.dev.tempHysteresis;
	(* Normal thermostat thresholds are independent from the absolute alarm limits. *)
	ec.dev.tempAboveSetpointBand := ec.dev.tempFeedback >= (ec.dev.tempSetpoint + ec.dev.tempHysteresis);
	ec.dev.tempBelowSetpointBand := ec.dev.tempFeedback <= (ec.dev.tempSetpoint - ec.dev.tempHysteresis);
	ec.dev.tempOverMax := ec.dev.tempFeedback > ec.dev.tempMax;
	ec.dev.tempOverMin := ec.dev.tempFeedback > ec.dev.tempMin;
	ec.dev.tempUnderMin := ec.dev.tempFeedback < ec.dev.tempMin;
	ec.dev.tempUnderMax := ec.dev.tempFeedback < ec.dev.tempMax;

	(* Process RH sensor *)
	ec.dev.rhAtSetpoint := ABS(ec.dev.rhFeedback - ec.dev.rhSetpoint) <= ec.dev.rhHysteresis;
	ec.dev.rhOverMax := ec.dev.rhFeedback > ec.dev.rhMax - ec.dev.rhHysteresis;
	ec.dev.rhUnderMin := ec.dev.rhFeedback < ec.dev.rhMin + ec.dev.rhHysteresis;
	ec.dev.rhOverMin := ec.dev.rhFeedback > ec.dev.rhMin;
	ec.dev.rhUnderMax := ec.dev.rhFeedback < ec.dev.rhMax;

	(* Duct sensor - safety predicates *)
	ec.dev.ductTempOverMax := ec.dev.ductTempFeedback > ec.dev.ductTempMax;
	ec.dev.ductTempUnderMin := ec.dev.ductTempFeedback < ec.dev.ductTempMin;
	ec.dev.ductRhOverMax := ec.dev.ductRhFeedback > ec.dev.ductRhMax;

	(*
	 * Process timing - run / break cycle.
	 *
	 * processActualDuration must NOT advance while the FSM is in Standby
	 * waiting for a phase to start (i.e. not in a break).
	 * If it did, isCompleted could fire while the process has not yet begun,
	 * causing the phase to complete immediately without doing any work.
	 *
	 * Counting rules:
	 *   Break (timeBreakEnabled=TRUE, status=Standby): advance processActualDuration + actualBreakDuration.
	 *   Active (status != Standby): advance processActualDuration + actualRuntime.
	 *   Idle (status=Standby, NOT timeBreakEnabled): no counters advance.
	 *)
	IF ec.clks.clock1s THEN
		IF ec.dev.timeBreakEnabled AND ec.dev.status = MainStatus.Standby THEN
			(* Break counting *)
			ec.dev.processActualDuration := ec.dev.processActualDuration + 1;
			ec.dev.actualBreakDuration := ec.dev.actualBreakDuration + 1;
			IF ec.dev.estimatedBreakDuration > 0 THEN
				(* Break ends when both minimum and estimated durations are met; reset counters for next run *)
				IF (ec.dev.actualBreakDuration >= ec.dev.estimatedBreakDuration)
						AND (ec.dev.actualBreakDuration >= ec.dev.minBreakDuration) THEN
					ec.dev.timeBreakEnabled := FALSE;
					ec.dev.actualRuntime := 0;
					ec.dev.actualBreakDuration := 0;
				END_IF;
			END_IF;
		ELSIF ec.dev.status <> MainStatus.Standby THEN
			(* Active run counting - only while the FSM is in an active phase state *)
			ec.dev.processActualDuration := ec.dev.processActualDuration + 1;
			ec.dev.actualRuntime := ec.dev.actualRuntime + 1;
			IF ec.dev.estimatedRuntime > 0 THEN
				ec.dev.processRemainingDuration := ec.dev.processEstimatedDuration - ec.dev.processActualDuration;
				IF NOT ec.dev.timeBreakEnabled
						AND (ec.dev.actualRuntime >= ec.dev.estimatedRuntime)
						AND (ec.dev.actualRuntime >= ec.dev.minRuntime) THEN
					ec.dev.timeBreakEnabled := TRUE;
					ec.dev.actualBreakDuration := 0;
				END_IF;
			END_IF;
		ELSIF (ec.dev.lastStatus = MainStatus.Cooling OR ec.dev.lastStatus = MainStatus.Heating)
				AND NOT ec.dev.isCompleted THEN
			(* Thermostat dwell between active cycles counts toward phase duration,
			 * but does not count as active runtime. *)
			ec.dev.processActualDuration := ec.dev.processActualDuration + 1;
			IF ec.dev.processEstimatedDuration > 0 THEN
				ec.dev.processRemainingDuration := ec.dev.processEstimatedDuration - ec.dev.processActualDuration;
			END_IF;
		END_IF;

		(* isCompleted is independent of the run/break cycle:
		 * a phase with only processEstimatedDuration set (no run/break) must also complete. *)
		IF ec.dev.processEstimatedDuration > 0 THEN
			ec.dev.isCompleted :=
				(ec.dev.processActualDuration >= ec.dev.processEstimatedDuration)
				AND (ec.dev.processActualDuration >= ec.dev.processMinDuration);
		END_IF;
	END_IF;

	(* Fault gate *)
	IF error OR ((ec.dev.signalMgmt.cumulativeOutputAction AND SignalOutputAction.ImmediateStop) <> 0) THEN
		ec.dev.faultRequest := TRUE;
		RETURN;
	END_IF;

	(*
	 * Transition-condition rule engine
	 *
	 * Persistence rule: every active-state CASE MUST end with
	 *   ELSE dev.standbyRequest := FALSE; (* keep current state alive *)
	 * to prevent the scan-level default (standbyRequest=TRUE) from immediately
	 * bouncing the FSM back to Standby before the exit condition is reached.
	 *)
	CASE ec.dev.status OF
	    (*
	     * Standby - decide next phase.
	     * Default standbyRequest=TRUE keeps the system here.
	     * Override when an external condition requires re-entering a phase.
	     *)
		MainStatus.Standby :
			(*
			 * Transition-condition evaluation order:
			 *   1. Safety overrides (cooling/heating if temperature out of limits).
			 *   2. Phase-resume conditions (dehumidification after break).
			 *   3. Fresh-start dehumidification (new recipe loaded, lastStatus=Standby after Init).
			 *   4. Hold-in-Standby (isCompleted) - checked LAST.
			 *
			 * isCompleted is evaluated last so that phase-transition conditions are always
			 * reachable.  The guard dev.lastStatus=Standby in condition 3 makes it safe:
			 * that guard is only TRUE after Init has run (Init sets dev.status=Standby, so
			 * line-97 lastStatus:=status writes Standby), which also resets isCompleted=FALSE.
			 * In the one-scan gap between a phase exit (isCompleted=TRUE, lastStatus=Cooling/
			 * Drying/…) and Init, lastStatus != Standby, so condition 3 cannot fire, and
			 * condition 4 correctly holds the FSM in Standby until configMgmt advances.
			 *)
			IF (ec.dev.lastStatus = MainStatus.Cooling OR ec.dev.lastStatus = MainStatus.Standby)
					AND ec.dev.tempAboveSetpointBand THEN
				(* Temperature above the thermostat band -> start/resume cooling. *)
				ec.dev.standbyRequest := FALSE;
				ec.dev.coolingRequest := TRUE;

			ELSIF (ec.dev.lastStatus = MainStatus.Heating OR ec.dev.lastStatus = MainStatus.Standby)
					AND ec.dev.tempBelowSetpointBand THEN
				(* Temperature below the thermostat band -> start/resume heating. *)
				ec.dev.standbyRequest := FALSE;
				ec.dev.heatingRequest := TRUE;

			ELSIF ec.dev.lastStatus = MainStatus.Drying
					AND NOT ec.dev.timeBreakEnabled
					AND NOT ec.dev.isCompleted
					AND ec.dev.tempInRange
					AND (NOT ec.dev.rhControlOnly
					OR (ec.dev.rhControlEnabled AND ec.dev.rhOverMax)) THEN
				(*
				 * End of break: resume dehumidification run when all conditions are met:
				 *   - break elapsed (NOT timeBreakEnabled)
				 *   - process not yet complete (NOT isCompleted)
				 *   - temperature back in process window (tempInRange)
				 *   - humidity still needs treatment
				 *)
				ec.dev.standbyRequest := FALSE;
				ec.dev.dryingRequest := TRUE;

			ELSIF ec.dev.lastStatus = MainStatus.Standby
					AND NOT ec.dev.tempOverMax
					AND ec.dev.rhOverMax THEN
				(*
				 * Fresh dehumidification recipe loaded: start when temperature is safe (<= tempMax)
				 * and humidity needs treatment.
				 *
				 * NOT tempOverMax (instead of tempInRange) eliminates the dead zone at
				 * tempFeedback in (tempMax-hyst, tempMax] that would leave the FSM stuck in
				 * Standby after a cooling phase delivered temp near the top of the window.
				 * If temp is below tempMin the Drying state switches to Heating temporarily,
				 * then returns to Drying once tempOverMin.
				 *)
				ec.dev.standbyRequest := FALSE;
				ec.dev.dryingRequest := TRUE;

			ELSIF ec.dev.isCompleted THEN
				ec.dev.standbyRequest := TRUE; (* Explicit: work done, hold here until configMgmt advances *)

			(* No ELSE needed here: standbyRequest=TRUE default holds Standby *)
			END_IF;

	    (*
	     * Ventilation - AHU + air flow only.
	     * No automatic exit; operator or recipe change triggers Standby.
	     *)
		MainStatus.Ventilation :
			IF ec.dev.isCompleted THEN
				ec.dev.standbyRequest := TRUE;
			ELSE
				ec.dev.standbyRequest := FALSE; (* Keep ventilating *)
			END_IF;

	    (*
	     * Cooling - cold group + AHU.
	     * Mode A: thermostat-only (no RH control).
	     * Mode B: with RH dehumidification - when RH reaches setpoint switch to Drying.
	     *
	     * EXIT conditions (standbyRequest=TRUE):
	     *   tempBelowSetpointBand -> lower thermostat threshold reached.
	     *   isCompleted -> work-effort complete.
	     * SWITCH conditions (standbyRequest=FALSE):
	     *   lastStatus=Drying + tempUnderMax -> resume dehumidification.
	     * ELSE -> keep cooling (temperature still above tempMin).
	     *)
		MainStatus.Cooling :
			IF ec.dev.tempBelowSetpointBand OR ec.dev.isCompleted THEN
				ec.dev.standbyRequest := TRUE;
			ELSIF ec.dev.lastStatus = MainStatus.Drying
					AND (ec.dev.tempUnderMax
					OR (ec.dev.rhControlEnabled AND ec.dev.rhOverMax AND ec.dev.tempUnderMax)) THEN
				ec.dev.standbyRequest := FALSE;
				ec.dev.dryingRequest := TRUE;
			ELSE
				ec.dev.standbyRequest := FALSE; (* Keep cooling - tempFeedback still above tempMin *)
			END_IF;

	    (*
	     * Heating - hot group + AHU.
	     * Mode C (no RH ctrl) / Mode D (with RH ctrl).
	     *
	     * EXIT: upper thermostat threshold reached or isCompleted.
	     * SWITCH to Drying: temperature restored to process window.
	     * ELSE: keep heating.
	     *)
		MainStatus.Heating :
			IF ec.dev.isCompleted OR ec.dev.tempAboveSetpointBand THEN
				ec.dev.standbyRequest := TRUE;
			ELSIF (ec.dev.lastStatus = MainStatus.Drying AND ec.dev.tempOverMin)
					OR (ec.dev.rhControlEnabled AND ec.dev.rhOverMax) THEN
				ec.dev.standbyRequest := FALSE;
				ec.dev.dryingRequest  := TRUE;
			ELSE
				ec.dev.standbyRequest := FALSE; (* Keep heating - tempFeedback still below tempMax *)
			END_IF;

	    (*
	     * Drying - cold + hot + AHU (Mode E / Mode F).
	     *
	     * Normal end conditions:
	     *   Time-based (!rhControlOnly): T in range AND runtime elapsed.
	     *   RH-only: RH <= rhMin AND minimum runtime elapsed.
	     *   RH+time: RH <= rhMin (timer managed externally).
	     *   isCompleted: work-effort done.
	     * Break trigger: timeBreakEnabled -> Standby (returns here after break).
	     * Override to Cooling: tempOverMax.
	     * Override to Heating: tempUnderMin.
	     * ELSE: keep dehumidifying.
	     *)
		MainStatus.Drying :
			IF ec.dev.isCompleted THEN
				ec.dev.standbyRequest := TRUE;
			ELSIF NOT ec.dev.rhControlOnly
					AND ec.dev.tempInRange
					AND (ec.dev.estimatedRuntime > 0)
					AND (ec.dev.actualRuntime > ec.dev.estimatedRuntime) THEN
				ec.dev.standbyRequest := TRUE; (* Time-based running completed *)
			ELSIF ec.dev.rhControlOnly
					AND ec.dev.rhUnderMin
					AND (ec.dev.actualRuntime >= ec.dev.minRuntime) THEN
				ec.dev.standbyRequest := TRUE; (* RH-only target reached *)
			ELSIF ec.dev.rhControlEnabled AND ec.dev.rhUnderMin THEN
				ec.dev.standbyRequest := TRUE; (* RH+time: humidity at minimum *)
			ELSIF ec.dev.timeBreakEnabled THEN
				ec.dev.standbyRequest := TRUE; (* Begin break - rule engine resumes Drying after break *)
			ELSIF ec.dev.tempOverMax THEN
				ec.dev.standbyRequest := FALSE;
				ec.dev.coolingRequest := TRUE;  (* Temporary cooling override *)
			ELSIF ec.dev.tempUnderMin THEN
				ec.dev.standbyRequest := FALSE;
				ec.dev.heatingRequest := TRUE;  (* Temporary heating override *)
			ELSE
				ec.dev.standbyRequest := FALSE; (* Keep dehumidifying - process ongoing *)
			END_IF;
	END_CASE;
	END_FUNCTION_BLOCK

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
	VAR_EXTERNAL
		clks : Clocks;
		dev : DeviceFacade;
		workEffort : WorkEffort;
	END_VAR
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
	dev.faultRequest := FALSE;
	dev.standbyRequest := TRUE;
	dev.heatingRequest := FALSE;
	dev.coolingRequest := FALSE;
	dev.ventilationRequest := FALSE;
	dev.dryingRequest := FALSE;

	deviceDiags(operationType := operationType, error => error);

	(* Compute sensor predicates *)

	(* Process temperature sensor *)
	dev.tempInRange := (dev.tempFeedback >= dev.tempMin + dev.tempHysteresis)
		AND (dev.tempFeedback <= dev.tempMax - dev.tempHysteresis);
	dev.tempAtSetpoint := ABS(dev.tempFeedback - dev.tempSetpoint) <= dev.tempHysteresis;
	dev.tempOverMax := dev.tempFeedback > dev.tempMax;
	dev.tempOverMin := dev.tempFeedback > dev.tempMin;
	dev.tempUnderMin := dev.tempFeedback < dev.tempMin;
	dev.tempUnderMax := dev.tempFeedback < dev.tempMax;

	(* Process RH sensor *)
	dev.rhAtSetpoint := ABS(dev.rhFeedback - dev.rhSetpoint) <= dev.rhHysteresis;
	dev.rhOverMax := dev.rhFeedback > dev.rhMax - dev.rhHysteresis;
	dev.rhUnderMin := dev.rhFeedback < dev.rhMin + dev.rhHysteresis;
	dev.rhOverMin := dev.rhFeedback > dev.rhMin;
	dev.rhUnderMax := dev.rhFeedback < dev.rhMax;

	(* Duct sensor - safety predicates *)
	dev.ductTempOverMax := dev.ductTempFeedback > dev.ductTempMax;
	dev.ductTempUnderMin := dev.ductTempFeedback < dev.ductTempMin;
	dev.ductRhOverMax := dev.ductRhFeedback > dev.ductRhMax;

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
	IF clks.clock1s THEN
		IF dev.timeBreakEnabled AND dev.status = MainStatus.Standby THEN
			(* Break counting *)
			dev.processActualDuration := dev.processActualDuration + 1;
			dev.actualBreakDuration := dev.actualBreakDuration + 1;
			IF dev.estimatedBreakDuration > 0 THEN
				(* Break ends when both minimum and estimated durations are met; reset counters for next run *)
				IF (dev.actualBreakDuration >= dev.estimatedBreakDuration)
						AND (dev.actualBreakDuration >= dev.minBreakDuration) THEN
					dev.timeBreakEnabled := FALSE;
					dev.actualRuntime := 0;
					dev.actualBreakDuration := 0;
				END_IF;
			END_IF;
		ELSIF dev.status <> MainStatus.Standby THEN
			(* Active run counting - only while the FSM is in an active phase state *)
			dev.processActualDuration := dev.processActualDuration + 1;
			dev.actualRuntime := dev.actualRuntime + 1;
			IF dev.estimatedRuntime > 0 THEN
				dev.processRemainingDuration := dev.processEstimatedDuration - dev.processActualDuration;
				IF NOT dev.timeBreakEnabled
						AND (dev.actualRuntime >= dev.estimatedRuntime)
						AND (dev.actualRuntime >= dev.minRuntime) THEN
					dev.timeBreakEnabled := TRUE;
					dev.actualBreakDuration := 0;
				END_IF;
			END_IF;
		ELSIF (dev.lastStatus = MainStatus.Cooling OR dev.lastStatus = MainStatus.Heating)
				AND NOT dev.isCompleted THEN
			(* Thermostat dwell between active cycles counts toward phase duration,
			 * but does not count as active runtime. *)
			dev.processActualDuration := dev.processActualDuration + 1;
			IF dev.processEstimatedDuration > 0 THEN
				dev.processRemainingDuration := dev.processEstimatedDuration - dev.processActualDuration;
			END_IF;
		END_IF;

		(* isCompleted is independent of the run/break cycle:
		 * a phase with only processEstimatedDuration set (no run/break) must also complete. *)
		IF dev.processEstimatedDuration > 0 THEN
			dev.isCompleted :=
				(dev.processActualDuration >= dev.processEstimatedDuration)
				AND (dev.processActualDuration >= dev.processMinDuration);
		END_IF;
	END_IF;

	(* Fault gate *)
	IF error OR ((dev.signalMgmt.cumulativeOutputAction AND SignalOutputAction.ImmediateStop) <> 0) THEN
		dev.faultRequest := TRUE;
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
	CASE dev.status OF
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
			IF (dev.lastStatus = MainStatus.Cooling OR dev.lastStatus = MainStatus.Standby)
					AND dev.tempOverMax THEN
				(* Temperature above limit -> start/resume cooling *)
				dev.standbyRequest := FALSE;
				dev.coolingRequest := TRUE;

			ELSIF (dev.lastStatus = MainStatus.Heating OR dev.lastStatus = MainStatus.Standby)
					AND dev.tempUnderMin THEN
				(* Temperature below limit -> start/resume heating *)
				dev.standbyRequest := FALSE;
				dev.heatingRequest := TRUE;

			ELSIF dev.lastStatus = MainStatus.Drying
					AND NOT dev.timeBreakEnabled
					AND NOT dev.isCompleted
					AND dev.tempInRange
					AND (NOT dev.rhControlOnly
					OR (dev.rhControlEnabled AND dev.rhOverMax)) THEN
				(*
				 * End of break: resume dehumidification run when all conditions are met:
				 *   - break elapsed (NOT timeBreakEnabled)
				 *   - process not yet complete (NOT isCompleted)
				 *   - temperature back in process window (tempInRange)
				 *   - humidity still needs treatment
				 *)
				dev.standbyRequest := FALSE;
				dev.dryingRequest := TRUE;

			ELSIF dev.lastStatus = MainStatus.Standby
					AND NOT dev.tempOverMax
					AND dev.rhOverMax THEN
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
				dev.standbyRequest := FALSE;
				dev.dryingRequest := TRUE;

			ELSIF dev.isCompleted THEN
				dev.standbyRequest := TRUE; (* Explicit: work done, hold here until configMgmt advances *)

			(* No ELSE needed here: standbyRequest=TRUE default holds Standby *)
			END_IF;

	    (*
	     * Ventilation - AHU + air flow only.
	     * No automatic exit; operator or recipe change triggers Standby.
	     *)
		MainStatus.Ventilation :
			IF dev.isCompleted THEN
				dev.standbyRequest := TRUE;
			ELSE
				dev.standbyRequest := FALSE; (* Keep ventilating *)
			END_IF;

	    (*
	     * Cooling - cold group + AHU.
	     * Mode A: thermostat-only (no RH control).
	     * Mode B: with RH dehumidification - when RH reaches setpoint switch to Drying.
	     *
	     * EXIT conditions (standbyRequest=TRUE):
	     *   tempUnderMin -> target reached, stop cooling.
	     *   isCompleted -> work-effort complete.
	     * SWITCH conditions (standbyRequest=FALSE):
	     *   lastStatus=Drying + tempUnderMax -> resume dehumidification.
	     * ELSE -> keep cooling (temperature still above tempMin).
	     *)
		MainStatus.Cooling :
			IF dev.tempUnderMin OR dev.isCompleted THEN
				dev.standbyRequest := TRUE;
			ELSIF dev.lastStatus = MainStatus.Drying
					AND (dev.tempUnderMax
					OR (dev.rhControlEnabled AND dev.rhOverMax AND dev.tempUnderMax)) THEN
				dev.standbyRequest := FALSE;
				dev.dryingRequest := TRUE;
			ELSE
				dev.standbyRequest := FALSE; (* Keep cooling - tempFeedback still above tempMin *)
			END_IF;

	    (*
	     * Heating - hot group + AHU.
	     * Mode C (no RH ctrl) / Mode D (with RH ctrl).
	     *
	     * EXIT: tempOverMax or isCompleted.
	     * SWITCH to Drying: temperature restored to process window.
	     * ELSE: keep heating.
	     *)
		MainStatus.Heating :
			IF dev.isCompleted OR dev.tempOverMax THEN
				dev.standbyRequest := TRUE;
			ELSIF (dev.lastStatus = MainStatus.Drying AND dev.tempOverMin)
					OR (dev.rhControlEnabled AND dev.rhOverMax) THEN
				dev.standbyRequest := FALSE;
				dev.dryingRequest  := TRUE;
			ELSE
				dev.standbyRequest := FALSE; (* Keep heating - tempFeedback still below tempMax *)
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
			IF dev.isCompleted THEN
				dev.standbyRequest := TRUE;
			ELSIF NOT dev.rhControlOnly
					AND dev.tempInRange
					AND (dev.estimatedRuntime > 0)
					AND (dev.actualRuntime > dev.estimatedRuntime) THEN
				dev.standbyRequest := TRUE; (* Time-based running completed *)
			ELSIF dev.rhControlOnly
					AND dev.rhUnderMin
					AND (dev.actualRuntime >= dev.minRuntime) THEN
				dev.standbyRequest := TRUE; (* RH-only target reached *)
			ELSIF dev.rhControlEnabled AND dev.rhUnderMin THEN
				dev.standbyRequest := TRUE; (* RH+time: humidity at minimum *)
			ELSIF dev.timeBreakEnabled THEN
				dev.standbyRequest := TRUE; (* Begin break - rule engine resumes Drying after break *)
			ELSIF dev.tempOverMax THEN
				dev.standbyRequest := FALSE;
				dev.coolingRequest := TRUE;  (* Temporary cooling override *)
			ELSIF dev.tempUnderMin THEN
				dev.standbyRequest := FALSE;
				dev.heatingRequest := TRUE;  (* Temporary heating override *)
			ELSE
				dev.standbyRequest := FALSE; (* Keep dehumidifying - process ongoing *)
			END_IF;
	END_CASE;
	END_FUNCTION_BLOCK

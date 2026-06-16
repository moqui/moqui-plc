(* Signal supervisor *)
FUNCTION_BLOCK SignalMgmt
VAR_EXTERNAL CONSTANT
	SIGNAL_LIST_MAX_SIZE : UINT;
END_VAR
VAR_INPUT
	operationType : SignalMgmtOperatingMode;
	(* Signal metadata *)
	code : INT; (* Unique ID for assigning a static priority to signals of the same category *)
	category : SignalCategory; (* Signal type: Static category/priority level + reset policy *)
	resetPol : ResetPolicy := ResetPolicy#UnconditionedReset;
	outputAction : DWORD := DWORD#16#0000; (* Response output/action to the signal detection *)
	(* Activation condition (condition of failure) or trigger policy for the signal, as a boolean expression *)
	activationCondition : BOOL;
	(*
	 * Condition for auto conditioned reset for the signal, as a boolean expression (e.g. MachineNotRunning).
	 * The reset condition or policy is considered only if an activation policy has
	 * been selected during the configuration phase.
	 *)
	autoResetCondition : BOOL;
	(* Reset commands *)
	reset : BOOL; (* Unconditioned manual/external reset *)
	auxReset : BOOL; (* Auxiliary key or command *)
	(* Selective reset *)
	selectiveResetTrigger : BOOL;
	selectiveResetCode : INT;
	(* Logger name for recording events associated with signals *)
	loggerName : STRING := '';
END_VAR
VAR_OUTPUT
	cumulativeOutputAction : DWORD := DWORD#16#0000; (* Cumulative output (stop) for the current cycle *)
	activeCategory : SignalCategory := SignalCategory#Information; (* Most severe category active *)
	(* Reset availability indicators (updated each cycle in Prepare+Process, for operator feedback) *)
	resetEnable : BOOL; (* TRUE if at least one active signal has cause gone and requires manual reset *)
	auxResetEnable : BOOL; (* TRUE if at least one active signal has cause gone and accepts aux reset *)
	error : BOOL := FALSE;
END_VAR
VAR
	(* Logger facade *)
	logger : LoggerFacade;
	(* Persistent signal log *)
	signalList : ARRAY[1..SIGNAL_LIST_MAX_SIZE] OF BOOL;
	(* Variables for detecting reset edges *)
	resetOld : BOOL;
	resetActivation : BOOL;
	auxResetOld : BOOL;
	auxResetActivation : BOOL;
	selectiveResetOld : BOOL;
	selectiveResetActivation : BOOL;
	requiresManualReset : BOOL;
	clearIndex : UINT;
END_VAR

(* Logger facade init *)
logger.enable := TRUE;
logger.loggerName := loggerName;

(* Args validation *)
IF loggerName = '' THEN
	error := TRUE;
	RETURN;
END_IF;

error := FALSE;

CASE operationType OF
	SignalMgmtOperatingMode#Reset :
		logger(message := 'Signal management reset.', level := LogLevel#Debug);
		clearIndex := UINT#1;
		WHILE clearIndex <= SIGNAL_LIST_MAX_SIZE DO
			signalList[clearIndex] := FALSE;
			clearIndex := clearIndex + UINT#1;
		END_WHILE;
		resetOld := FALSE;
		auxResetOld := FALSE;
		selectiveResetOld := FALSE;
		cumulativeOutputAction := DWORD#16#0000;
		activeCategory := SignalCategory#Information;
		resetEnable := FALSE;
		auxResetEnable := FALSE;

	SignalMgmtOperatingMode#Prepare :
		(* Detection of reset edges valid for the entire cycle *)
		resetActivation := reset AND NOT resetOld;
		resetOld := reset;
		auxResetActivation := auxReset AND NOT auxResetOld;
		auxResetOld := auxReset;
		selectiveResetActivation := selectiveResetTrigger AND NOT selectiveResetOld;
		selectiveResetOld := selectiveResetTrigger;
		(* Init for the current cycle *)
		cumulativeOutputAction := DWORD#16#0000;
		activeCategory := SignalCategory#Information;
		resetEnable := FALSE;
		auxResetEnable := FALSE;

	SignalMgmtOperatingMode#Process :
		(* Bounds check *)
		IF (code < 1) OR (TO_UINT(code) > SIGNAL_LIST_MAX_SIZE) THEN
			error := TRUE;
			RETURN;
		END_IF;

		(*
		 * Determine if manual reset is required.
		 * - Alarm, Anomaly: require manual reset unless resetPol = AutoReset
		 * - Warning, Information: always auto-reset
		 *)
		CASE category OF
			SignalCategory#Alarm,
			SignalCategory#Anomaly :
				requiresManualReset := (resetPol <> ResetPolicy#AutoReset);
			SignalCategory#Warning,
			SignalCategory#Information :
				requiresManualReset := FALSE;
		END_CASE;

		(* Check the activation condition *)
		IF activationCondition AND NOT signalList[code] THEN
			signalList[code] := TRUE;
			logger(message := 'Signal active.', level := LogLevel#Fatal);
		END_IF;

		(*
		 * Reset logic.
		 * An active signal is reset if the physical cause has disappeared (NOT activationCondition)
		 * AND one of the following re-entry conditions occurs, filtered by resetPol:
		 *   - Auto-reset (Warning/Information, or Alarm/Anomaly with AutoReset policy)
		 *   - Unconditioned manual reset: always allowed for Alarm
		 *   - Aux reset: only if resetPol = AuxReset
		 *   - Conditioned reset: only if resetPol = AutoConditionedReset / AutoProvisionalReset / AutoPriorityReset
		 *   - Selective reset: always allowed (supervisor override)
		 *)
		IF NOT activationCondition AND signalList[code] THEN
			IF NOT requiresManualReset THEN
				(* Auto-reset: Warning, Information, or Alarm/Anomaly with AutoReset policy *)
				signalList[code] := FALSE;
			ELSIF resetActivation THEN
				(* Unconditioned manual reset *)
				signalList[code] := FALSE;
			ELSIF auxResetActivation AND (resetPol = ResetPolicy#AuxReset) THEN
				(* Aux reset: only if explicitly configured *)
				signalList[code] := FALSE;
			ELSIF autoResetCondition AND (
					(resetPol = ResetPolicy#AutoConditionedReset) OR
					(resetPol = ResetPolicy#AutoProvisionalReset) OR
					(resetPol = ResetPolicy#AutoPriorityReset)) THEN
				(* Conditioned reset: only if explicitly configured *)
				signalList[code] := FALSE;
			ELSIF selectiveResetActivation AND (selectiveResetCode = code) THEN
				(* Selective reset from external supervision: always allowed *)
				signalList[code] := FALSE;
			END_IF;

			IF NOT signalList[code] THEN
				logger(message := 'Signal reset.');
			END_IF;
		END_IF;

		(* Cumulative stop bitmask *)
		IF signalList[code] THEN
			cumulativeOutputAction := cumulativeOutputAction OR outputAction;

			(* Track the most severe category active in this cycle *)
			CASE category OF
				SignalCategory#Alarm :
					activeCategory := SignalCategory#Alarm;
				SignalCategory#Anomaly :
					IF (activeCategory = SignalCategory#Warning) OR
							(activeCategory = SignalCategory#Information) THEN
						activeCategory := SignalCategory#Anomaly;
					END_IF;
				SignalCategory#Warning :
					IF activeCategory = SignalCategory#Information THEN
						activeCategory := SignalCategory#Warning;
					END_IF;
				SignalCategory#Information :
					activeCategory := activeCategory;
			END_CASE;
		END_IF;

		(* Reset availability: signal is active, cause is gone, manual reset is required *)
		IF signalList[code] AND NOT activationCondition AND requiresManualReset THEN
			resetEnable := TRUE;
		END_IF;
		IF signalList[code] AND NOT activationCondition AND (resetPol = ResetPolicy#AuxReset) THEN
			auxResetEnable := TRUE;
		END_IF;
END_CASE;
END_FUNCTION_BLOCK

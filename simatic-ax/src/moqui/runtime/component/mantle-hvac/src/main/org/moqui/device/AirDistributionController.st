(*
 * AirDistributionController: Logical sequencer for alternating high/low air throw.
 *
 * Implements cumulative timing logic for throw phases:
 * - Time advances only during active operation (operationType = Run AND enable = TRUE).
 * - Counters are frozen (retained) during standby/pause phases.
 * - Implements a Make-Before-Break transition between ducts to prevent overpressure peaks,
 * leveraging the asynchronous handshake mechanism (VAR_IN_OUT) of the underlying Actuator instances.
 *)
FUNCTION_BLOCK AirDistributionController
	VAR_EXTERNAL
	    dev : DeviceFacade;
	END_VAR
	VAR_INPUT
	    operationType : OperatingMode := OperatingMode#Init;
	    enable : BOOL; (* Local run permission (e.g., air flow running + air mixing enabled) *)
	    clock1s : BOOL; (* 1-second base clock pulse *)
	END_VAR
	VAR CONSTANT
	    componentName : STRING := 'AirDistributionController';
	END_VAR
	VAR
		(* Logger facade *)
	    logger : LoggerFacade;
	    status : AirDistributionControllerStatus := AirDistributionControllerStatus#Init;
	    cumulatedTimeHigh : UINT := UINT#0;
	    cumulatedTimeLow : UINT := UINT#0;
	END_VAR

	(* Logger facade init *)
	logger.enable := TRUE; logger.loggerName := componentName;

	(* Initialization or reset upon critical Stop *)
	IF operationType = OperatingMode#Init THEN
	    logger(message := 'Init air distribution controller.', level := LogLevel#DEBUG);
	    status := AirDistributionControllerStatus#Init;
	    cumulatedTimeHigh := UINT#0;
	    cumulatedTimeLow := UINT#0;
		dev.highFlowDamperEnableRequest := TRUE;
		dev.highFlowDamperDisableRequest := FALSE;
		dev.lowFlowDamperEnableRequest := FALSE;
		dev.lowFlowDamperDisableRequest := TRUE;
	    RETURN;
	END_IF;

	(* Logic advances ONLY if the system is in Run mode and local enable is active *)
	IF (operationType = OperatingMode#Run) AND enable THEN
    
	    CASE status OF
        
	        AirDistributionControllerStatus#Init:
	            (* Startup sequence: defaults to the high throw phase *)
	            dev.highFlowDamperEnableRequest := TRUE;
	 		   	dev.highFlowDamperDisableRequest := FALSE;
	            dev.lowFlowDamperEnableRequest := FALSE;
	 		   	dev.lowFlowDamperDisableRequest := TRUE;
	            logger(message := 'Enter high throw phase.', level := LogLevel#DEBUG);
	            status := AirDistributionControllerStatus#HighPhase;

	        AirDistributionControllerStatus#HighPhase:
	            (* Advance cumulative timer *)
	            IF clock1s THEN
	                cumulatedTimeHigh := cumulatedTimeHigh + UINT#1;
	            END_IF;
            
	            (* Evaluate switching threshold *)
	            IF dev.setPointTimeHigh > UINT#0 AND cumulatedTimeHigh >= dev.setPointTimeHigh THEN
	                cumulatedTimeHigh := UINT#0;
	                (* Make-Before-Break Interlock / Asynchronous Handshake *)
					dev.highFlowDamperEnableRequest := FALSE;
					dev.highFlowDamperDisableRequest := TRUE;
					dev.lowFlowDamperEnableRequest := TRUE;
					dev.lowFlowDamperDisableRequest := FALSE;
	                logger(message := 'Transition to low throw.', level := LogLevel#DEBUG);
	                status := AirDistributionControllerStatus#TransitionToLow;
	            END_IF;

	        AirDistributionControllerStatus#TransitionToLow:
	            (* * Monitor the falling edge of the request signals.
	             * The Actuator block internally clears the VAR_IN_OUT variable once 
	             * the physical maneuver is completed. This ensures the sequencer 
	             * advances only after the hardware has reached its target position.
	             *)
	            IF NOT dev.highFlowDamperDisableRequest AND NOT dev.lowFlowDamperEnableRequest THEN
	                logger(message := 'Enter low throw phase.', level := LogLevel#DEBUG);
	                status := AirDistributionControllerStatus#LowPhase;
	            END_IF;

	        AirDistributionControllerStatus#LowPhase:
	            (* Advance cumulative timer *)
	            IF clock1s THEN
	                cumulatedTimeLow := cumulatedTimeLow + UINT#1;
	            END_IF;
            
	            (* Evaluate switching threshold *)
	            IF dev.setPointTimeLow > UINT#0 AND cumulatedTimeLow >= dev.setPointTimeLow THEN
	                cumulatedTimeLow := UINT#0;
	                (* Make-Before-Break Interlock / Asynchronous Handshake *)
					dev.highFlowDamperEnableRequest := TRUE;
					dev.highFlowDamperDisableRequest := FALSE;
					dev.lowFlowDamperEnableRequest := FALSE;
					dev.lowFlowDamperDisableRequest := TRUE;
	                logger(message := 'Transition to high throw.', level := LogLevel#DEBUG);
	                status := AirDistributionControllerStatus#TransitionToHigh;
	            END_IF;
            
	        AirDistributionControllerStatus#TransitionToHigh:
	            (* Wait for hardware positioning confirmation *)
	            IF NOT dev.lowFlowDamperDisableRequest AND NOT dev.highFlowDamperEnableRequest THEN
	                logger(message := 'Enter high throw phase.', level := LogLevel#DEBUG);
	                status := AirDistributionControllerStatus#HighPhase;
	            END_IF;
	    END_CASE;
	ELSE
	    (* Standby / Pause Condition *)
	    (* 
	     * During standby (OperatingMode#Standby OR enable = FALSE), the FB does 
	     * not increment any timers. The current status and Request variables are 
	     * frozen, maintaining the hardware in its last consolidated stable state.
	     *)
	    ;
	END_IF;
	END_FUNCTION_BLOCK

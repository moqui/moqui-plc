(* 
 * NOTE: In general, the Main component implements the control logic of automated industrial systems (Finite State Machine - FSM)
 * using hierarchical control architectures. It separates control policies from implementation mechanisms,
 * and diagnostic mechanisms from failure/error reaction and system reset policies.
*)

(* Example of a supervisor FSM for a civil HVAC air-handling unit (AHU).
 *
 * Topology:
 *   Mode A Thermostat cooling -> Cooling
 *   Mode B Cooling with RH% dehumidification -> Cooling  (rhControlEnabled=TRUE)
 *   Mode C Winter heating -> Heating
 *   Mode D Heating with RH% control -> Heating (rhControlEnabled=TRUE)
 *   Mode E Interval dehumidification (on/off) -> Drying
 *   Mode F Dehumidification by RH% target -> Drying (rhControlEnabled=TRUE)
 *
 * Output function - which device groups are enabled per state:
 *
 *   State          Cold Group   Hot Group   AHU Fan   Air Flow
 *   -
 *   Standby            OFF         OFF        OFF       OFF
 *   Ventilation        OFF         OFF        ON        ON
 *   Cooling            ON          OFF        ON        ON
 *   Heating            OFF         ON         ON        ON
 *   Drying             ON          ON         ON        ON
 *   Fault              OFF         OFF        OFF       OFF
 *
 * MainRuleEngine generates transition requests; Main consumes them.
 * DeviceManager orchestrates the individual device FBs.
 *
 * Call order in the PLC task:
 *   InputSignalUpdate -> Main -> DeviceManager -> OutputSignalUpdate
 *)
FUNCTION_BLOCK Main
	
	VAR_INPUT
		operationType : OperatingMode;
		enable : BOOL;
		deviceConfigContextResetRequest : BOOL := FALSE;
	END_VAR
	VAR_OUTPUT
		done : BOOL;
		error : BOOL;
	END_VAR
	VAR CONSTANT
		componentName : STRING := 'HVAC_DEMO_PLC';
	END_VAR
	VAR
		(* Logger facade *)
		logger : LoggerFacade;
		(* FSM transition logic *)
		ruleEngine : MainRuleEngine;
		(* Define a nested FSMs for managing air distribution subsystem. *)
		airDistribCtrl : AirDistributionController;
		(* HAL manager *)
		deviceManager : DeviceManager;
		(* Periodic logical-parameter logger *)
		logParameters : ParameterLogger;
	END_VAR

	(* Logger facade init *)
	logger.enable := TRUE; logger.loggerName := componentName;

	IF NOT enable THEN RETURN; END_IF

	(* Init: device setup and configuration *)
	IF (operationType = operatingMode.Init) THEN
		logger(message := 'Setup and configuration of all devices.', level := LogLevel.DEBUG);
		(*
	     * The static device configuration parameters are mapped directly by the device config manager (recipe manager),
		 * while only the dynamic parameters are mapped below in the standby status.
		 *)
		(* Reset signal manager *)
		ec.dev.signalMgmt(operationType := SignalMgmtOperatingMode.Reset, loggerName := componentName);
		ec.dev.status := MainStatus.Standby;
		ec.dev.actualRuntime := 0;
		ec.dev.actualBreakDuration := 0;
		ec.dev.processActualDuration := 0;
		ec.dev.processRemainingDuration := 0;
		ec.dev.timeBreakEnabled := FALSE;
		ec.dev.isCompleted := FALSE;
		airDistribCtrl(operationType := OperatingMode.Init, enable := FALSE, clock1s := FALSE);
		done := FALSE;
	ELSIF deviceConfigContextResetRequest THEN
		logger(message := 'Reset HVAC device config context.', level := LogLevel.DEBUG);
		(*
	     * Lightweight reset between recipes: keep device init/homing in the Init path,
		 * but clear runtime state inherited from the previous device config.
	     *)
		ec.dev.status := MainStatus.Standby;
		ec.dev.lastStatus := MainStatus.Standby;
		ec.dev.actualRuntime := 0;
		ec.dev.actualBreakDuration := 0;
		ec.dev.processActualDuration := 0;
		ec.dev.processRemainingDuration := 0;
		ec.dev.timeBreakEnabled := FALSE;
		ec.dev.isCompleted := FALSE;
		airDistribCtrl(operationType := OperatingMode.Init, enable := FALSE, clock1s := FALSE);
		done := FALSE;
	ELSE
		(* FSM transition-condition rule engine *)
		logger(message := 'Run FSM transition-condition logic.', level := LogLevel.DEBUG);
		ruleEngine(operationType := operationType);	
	END_IF;

		(*
		 * Preserve the originating phase while idling in Standby so thermostat-driven
		 * Heating/Cooling recipes can stop/start repeatedly until isCompleted becomes TRUE.
		 * Init still stamps Standby, which keeps fresh-start logic for a newly loaded recipe.
	     *)
		IF (operationType = OperatingMode.Init) OR (ec.dev.status <> MainStatus.Standby) THEN
			ec.dev.lastStatus := ec.dev.status;
		END_IF;

	(* Fault overrides any other state *)
	IF ec.dev.faultRequest THEN ec.dev.status := MainStatus.Fault; END_IF;

	(* Main FSM - Output function + State-update function *)
	logger(message := 'Run Main FSM.', level := LogLevel.DEBUG);
	CASE ec.dev.status OF
	    (* Standby / Homing: all groups off, wait for the next phase request. *)
		MainStatus.Standby :
			logger(message := 'Standby.', level := LogLevel.DEBUG);
			ec.dev.standbyRequest := FALSE;

			(* FSM Output function - everything disabled *)
			ec.dev.coldGroupEnableRequest := FALSE;
			ec.dev.coldGroupDisableRequest := TRUE;
			ec.dev.hotGroupEnableRequest := FALSE;
			ec.dev.hotGroupDisableRequest := TRUE;
			ec.dev.ahuFanEnableRequest := FALSE;
			ec.dev.airFlowEnableRequest := FALSE;
			ec.dev.airFlowDisableRequest := TRUE;
		
			(* FSM status update function *)
			IF ec.dev.ventilationRequest THEN
				ec.dev.status := MainStatus.Ventilation;
			ELSIF ec.dev.coolingRequest THEN
				ec.dev.status := MainStatus.Cooling;
			ELSIF ec.dev.heatingRequest THEN
				ec.dev.status := MainStatus.Heating;
			ELSIF ec.dev.dryingRequest THEN
				ec.dev.status := MainStatus.Drying;
			END_IF;

	    (* Ventilation: AHU + air flow control only - no temperature conditioning. *)
		MainStatus.Ventilation :
			logger(message := 'Ventilation.', level := LogLevel.DEBUG);
			ec.dev.ventilationRequest := FALSE;

			(* FSM output function *)
			ec.dev.coldGroupEnableRequest := FALSE;
			ec.dev.coldGroupDisableRequest := TRUE;
			ec.dev.hotGroupEnableRequest := FALSE;
			ec.dev.hotGroupDisableRequest := TRUE;
			ec.dev.ahuFanEnableRequest := TRUE;
			ec.dev.airFlowEnableRequest := TRUE;
			ec.dev.airFlowDisableRequest := FALSE;
		
			(* FSM status update function *)
			IF ec.dev.standbyRequest THEN
				ec.dev.status := MainStatus.Standby;
			ELSIF ec.dev.coolingRequest THEN
				ec.dev.status := MainStatus.Cooling;
			ELSIF ec.dev.heatingRequest THEN
				ec.dev.status := MainStatus.Heating;
			ELSIF ec.dev.dryingRequest THEN
				ec.dev.status := MainStatus.Drying;
			END_IF;

	    (*
	     * Cooling: cold group + AHU + air flow control.
	     * Mode A (no RH ctrl) and Mode B (with RH dehumidification, rhControlEnabled=TRUE).
	     * In Mode B the hot group is also enabled to re-heat after dehumidification;
	     * that secondary enable is issued by MainRuleEngine via heatingRequest/dryingRequest
	     * transitions rather than here, keeping output function clean.
	     *)
		MainStatus.Cooling :
			logger(message := 'Cooling.', level := LogLevel.DEBUG);
			ec.dev.coolingRequest := FALSE;

			(* FSM output function *)
			ec.dev.coldGroupEnableRequest := TRUE;
			ec.dev.coldGroupDisableRequest := FALSE;
			ec.dev.hotGroupEnableRequest := FALSE;
			ec.dev.hotGroupDisableRequest := TRUE;
			ec.dev.ahuFanEnableRequest := TRUE;
			ec.dev.airFlowEnableRequest := TRUE;
			ec.dev.airFlowDisableRequest := FALSE;
		
			(* FSM status update function *)
			IF ec.dev.standbyRequest THEN
				ec.dev.status := MainStatus.Standby;
			ELSIF ec.dev.dryingRequest THEN
				ec.dev.status := MainStatus.Drying;
			ELSIF ec.dev.ventilationRequest THEN
				ec.dev.status := MainStatus.Ventilation;
			END_IF;

	    (*
	     * Heating: hot group + AHU + air flow control.
	     * Mode C (no RH ctrl) and Mode D (with RH ctrl).
	     *)
		MainStatus.Heating :
			logger(message := 'Heating.', level := LogLevel.DEBUG);
			ec.dev.heatingRequest := FALSE;

			(* FSM output function *)
			ec.dev.coldGroupEnableRequest := FALSE;
			ec.dev.coldGroupDisableRequest := TRUE;
			ec.dev.hotGroupEnableRequest := TRUE;
			ec.dev.hotGroupDisableRequest := FALSE;
			ec.dev.ahuFanEnableRequest := TRUE;
			ec.dev.airFlowEnableRequest := TRUE;
			ec.dev.airFlowDisableRequest := FALSE;

			(* FSM status update function *)
			IF ec.dev.standbyRequest THEN
				ec.dev.status := MainStatus.Standby;
			ELSIF ec.dev.dryingRequest THEN
				ec.dev.status := MainStatus.Drying;
			ELSIF ec.dev.ventilationRequest THEN
				ec.dev.status := MainStatus.Ventilation;
			END_IF;

	    (*
	     * Drying: cold + hot + AHU + air flow control.
	     * Mode E (interval on/off) and Mode F (RH% controlled).
	     * During break the rule engine transitions to Standby; returns here
	     * when the break is complete.
	     *)
		MainStatus.Drying :
			logger(message := 'Drying.', level := LogLevel.DEBUG);
			ec.dev.dryingRequest := FALSE;

			(* FSM output function *)
			ec.dev.coldGroupEnableRequest := TRUE;
			ec.dev.coldGroupDisableRequest := FALSE;
			ec.dev.hotGroupEnableRequest := TRUE;
			ec.dev.hotGroupDisableRequest := FALSE;
			ec.dev.ahuFanEnableRequest := TRUE;
			ec.dev.airFlowEnableRequest := TRUE;
			ec.dev.airFlowDisableRequest := FALSE;

			(* FSM status update function *)
			IF ec.dev.standbyRequest THEN
				ec.dev.status := MainStatus.Standby;
			ELSIF ec.dev.heatingRequest THEN
				ec.dev.status := MainStatus.Heating;
			ELSIF ec.dev.coolingRequest THEN
				ec.dev.status := MainStatus.Cooling;
			ELSIF ec.dev.ventilationRequest THEN
				ec.dev.status := MainStatus.Ventilation;
			END_IF;

	    (* Fault: all groups off; wait for signal manager to clear all alarms. *)
		MainStatus.Fault :
			logger(message := 'Fault.', level := LogLevel.DEBUG);
			ec.dev.faultRequest := FALSE;

			(* FSM output function *)
			error := TRUE;
			ec.dev.coldGroupEnableRequest := FALSE;
			ec.dev.coldGroupDisableRequest := TRUE;
			ec.dev.hotGroupEnableRequest := FALSE;
			ec.dev.hotGroupDisableRequest := TRUE;
			ec.dev.ahuFanEnableRequest := FALSE;
			ec.dev.airFlowEnableRequest := FALSE;
			ec.dev.airFlowDisableRequest := TRUE;

			(* Return to Standby only when all alarms have been cleared *)
			IF (ec.dev.signalMgmt.cumulativeOutputAction = SignalOutputAction.None) THEN
				error := FALSE;
				ec.dev.status := MainStatus.Standby;
			END_IF;
	END_CASE;

	(*
	 * Air distribution is a subordinate subsystem:
	 * it runs only when the main FSM requests air flow and the recipe explicitly
	 * enables alternating high/low air distribution.
	 *)
	airDistribCtrl(
		operationType := operationType,
		enable := ec.dev.airFlowEnableRequest AND ec.dev.airDistributionEnabled,
		clock1s := ec.clks.clock1s);

	done := ec.dev.isCompleted;

	(* Device orchestration (HAL) *)
	logger(message := 'Update HVAC devices.', level := LogLevel.DEBUG);
	deviceManager(operationType := operationType);

	(* Log the coherent post-device-update parameter snapshot. *)
	logParameters(operationType := operationType);
	END_FUNCTION_BLOCK

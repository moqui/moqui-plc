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
	VAR_EXTERNAL
		dev : DeviceFacade;
		workEffort : WorkEffort;
	END_VAR
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
		componentName : STRING := 'hvac';
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
		dev.signalMgmt(operationType := SignalMgmtOperatingMode.Reset, loggerName := componentName);
		dev.status := MainStatus.Standby;
		dev.actualRuntime := 0;
		dev.actualBreakDuration := 0;
		dev.processActualDuration := 0;
		dev.processRemainingDuration := 0;
		dev.timeBreakEnabled := FALSE;
		dev.isCompleted := FALSE;
		airDistribCtrl(operationType := OperatingMode.Init, enable := FALSE, clock1s := FALSE);
		done := FALSE;
	ELSIF deviceConfigContextResetRequest THEN
		logger(message := 'Reset HVAC device config context.', level := LogLevel.DEBUG);
		(*
	     * Lightweight reset between recipes: keep device init/homing in the Init path,
		 * but clear runtime state inherited from the previous device config.
	     *)
		dev.status := MainStatus.Standby;
		dev.lastStatus := MainStatus.Standby;
		dev.actualRuntime := 0;
		dev.actualBreakDuration := 0;
		dev.processActualDuration := 0;
		dev.processRemainingDuration := 0;
		dev.timeBreakEnabled := FALSE;
		dev.isCompleted := FALSE;
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
		IF (operationType = OperatingMode.Init) OR (dev.status <> MainStatus.Standby) THEN
			dev.lastStatus := dev.status;
		END_IF;

	(* Fault overrides any other state *)
	IF dev.faultRequest THEN dev.status := MainStatus.Fault; END_IF;

	(* Main FSM - Output function + State-update function *)
	logger(message := 'Run Main FSM.', level := LogLevel.DEBUG);
	CASE dev.status OF
	    (* Standby / Homing: all groups off, wait for the next phase request. *)
		MainStatus.Standby :
			logger(message := 'Standby.', level := LogLevel.DEBUG);
			dev.standbyRequest := FALSE;

			(* FSM Output function - everything disabled *)
			dev.coldGroupEnableRequest := FALSE;
			dev.coldGroupDisableRequest := TRUE;
			dev.hotGroupEnableRequest := FALSE;
			dev.hotGroupDisableRequest := TRUE;
			dev.ahuFanEnableRequest := FALSE;
			dev.airFlowEnableRequest := FALSE;
			dev.airFlowDisableRequest := TRUE;
		
			(* FSM status update function *)
			IF dev.ventilationRequest THEN
				dev.status := MainStatus.Ventilation;
			ELSIF dev.coolingRequest THEN
				dev.status := MainStatus.Cooling;
			ELSIF dev.heatingRequest THEN
				dev.status := MainStatus.Heating;
			ELSIF dev.dryingRequest THEN
				dev.status := MainStatus.Drying;
			END_IF;

	    (* Ventilation: AHU + air flow control only - no temperature conditioning. *)
		MainStatus.Ventilation :
			logger(message := 'Ventilation.', level := LogLevel.DEBUG);
			dev.ventilationRequest := FALSE;

			(* FSM output function *)
			dev.coldGroupEnableRequest := FALSE;
			dev.coldGroupDisableRequest := TRUE;
			dev.hotGroupEnableRequest := FALSE;
			dev.hotGroupDisableRequest := TRUE;
			dev.ahuFanEnableRequest := TRUE;
			dev.airFlowEnableRequest := TRUE;
			dev.airFlowDisableRequest := FALSE;
		
			(* FSM status update function *)
			IF dev.standbyRequest THEN
				dev.status := MainStatus.Standby;
			ELSIF dev.coolingRequest THEN
				dev.status := MainStatus.Cooling;
			ELSIF dev.heatingRequest THEN
				dev.status := MainStatus.Heating;
			ELSIF dev.dryingRequest THEN
				dev.status := MainStatus.Drying;
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
			dev.coolingRequest := FALSE;

			(* FSM output function *)
			dev.coldGroupEnableRequest := TRUE;
			dev.coldGroupDisableRequest := FALSE;
			dev.hotGroupEnableRequest := FALSE;
			dev.hotGroupDisableRequest := TRUE;
			dev.ahuFanEnableRequest := TRUE;
			dev.airFlowEnableRequest := TRUE;
			dev.airFlowDisableRequest := FALSE;
		
			(* FSM status update function *)
			IF dev.standbyRequest THEN
				dev.status := MainStatus.Standby;
			ELSIF dev.dryingRequest THEN
				dev.status := MainStatus.Drying;
			ELSIF dev.ventilationRequest THEN
				dev.status := MainStatus.Ventilation;
			END_IF;

	    (*
	     * Heating: hot group + AHU + air flow control.
	     * Mode C (no RH ctrl) and Mode D (with RH ctrl).
	     *)
		MainStatus.Heating :
			logger(message := 'Heating.', level := LogLevel.DEBUG);
			dev.heatingRequest := FALSE;

			(* FSM output function *)
			dev.coldGroupEnableRequest := FALSE;
			dev.coldGroupDisableRequest := TRUE;
			dev.hotGroupEnableRequest := TRUE;
			dev.hotGroupDisableRequest := FALSE;
			dev.ahuFanEnableRequest := TRUE;
			dev.airFlowEnableRequest := TRUE;
			dev.airFlowDisableRequest := FALSE;

			(* FSM status update function *)
			IF dev.standbyRequest THEN
				dev.status := MainStatus.Standby;
			ELSIF dev.dryingRequest THEN
				dev.status := MainStatus.Drying;
			ELSIF dev.ventilationRequest THEN
				dev.status := MainStatus.Ventilation;
			END_IF;

	    (*
	     * Drying: cold + hot + AHU + air flow control.
	     * Mode E (interval on/off) and Mode F (RH% controlled).
	     * During break the rule engine transitions to Standby; returns here
	     * when the break is complete.
	     *)
		MainStatus.Drying :
			logger(message := 'Drying.', level := LogLevel.DEBUG);
			dev.dryingRequest := FALSE;

			(* FSM output function *)
			dev.coldGroupEnableRequest := TRUE;
			dev.coldGroupDisableRequest := FALSE;
			dev.hotGroupEnableRequest := TRUE;
			dev.hotGroupDisableRequest := FALSE;
			dev.ahuFanEnableRequest := TRUE;
			dev.airFlowEnableRequest := TRUE;
			dev.airFlowDisableRequest := FALSE;

			(* FSM status update function *)
			IF dev.standbyRequest THEN
				dev.status := MainStatus.Standby;
			ELSIF dev.heatingRequest THEN
				dev.status := MainStatus.Heating;
			ELSIF dev.coolingRequest THEN
				dev.status := MainStatus.Cooling;
			ELSIF dev.ventilationRequest THEN
				dev.status := MainStatus.Ventilation;
			END_IF;

	    (* Fault: all groups off; wait for signal manager to clear all alarms. *)
		MainStatus.Fault :
			logger(message := 'Fault.', level := LogLevel.DEBUG);
			dev.faultRequest := FALSE;

			(* FSM output function *)
			error := TRUE;
			dev.coldGroupEnableRequest := FALSE;
			dev.coldGroupDisableRequest := TRUE;
			dev.hotGroupEnableRequest := FALSE;
			dev.hotGroupDisableRequest := TRUE;
			dev.ahuFanEnableRequest := FALSE;
			dev.airFlowEnableRequest := FALSE;
			dev.airFlowDisableRequest := TRUE;

			(* Return to Standby only when all alarms have been cleared *)
			IF (dev.signalMgmt.cumulativeOutputAction = SignalOutputAction.None) THEN
				error := FALSE;
				dev.status := MainStatus.Standby;
			END_IF;
	END_CASE;

	(*
	 * Air distribution is a subordinate subsystem:
	 * it runs only when the main FSM requests air flow and the recipe explicitly
	 * enables alternating high/low air distribution.
	 *)
	airDistribCtrl(
		operationType := operationType,
		enable := dev.airFlowEnableRequest AND dev.airDistributionEnabled,
		clock1s := clks.clock1s);

	done := dev.isCompleted;

	(* Device orchestration (HAL) *)
	logger(message := 'Update HVAC devices.', level := LogLevel.DEBUG);
	deviceManager(operationType := operationType);
	END_FUNCTION_BLOCK

PROGRAM MoquiStart
	VAR_EXTERNAL CONSTANT
		applicationDeviceId : STRING;
		retryOnError : BOOL;
		minRetryTime, maxRetryCount : UINT;
	END_VAR
	VAR_EXTERNAL
		clks : Clocks;
		enable, init, error, reset : BOOL;
		allConfigLoaded : BOOL;
		retryCount, retryTime : UINT;	
	END_VAR
	VAR
		operationType : OperatingMode := OperatingMode.Init;
		status : MoquiStartStatus := MoquiStartStatus.Idle;
		(* Main framework components *)
		logger : LoggerFacade;
		runNetworkDgs : NetworkDiagnostics;
		clockGen : ClockGeneration;
		inputProcessing : InputSignalUpdate;
		outputProcessing : OutputSignalUpdate;
		(* Device config (recipe) management *)
		configMgmt : DeviceConfigMgmt;
		(* Application component *)
		main : Main;
		mainDone : BOOL;
		mainDoneREdge : R_TRIG;
		deviceConfigContextResetRequest : BOOL;
		(*
	     * Keep one Init cycle pending for Main after the first device config has
		 * been loaded, because recipe data also contains device init/homing params.
	     *)
		mainInitPending : BOOL := TRUE;
	END_VAR

	(* Set the operating mode *)
	IF ec.init THEN
		(* Logger facade init *)
		logger.enable := TRUE; logger.loggerName := applicationDeviceId;
		operationType := OperatingMode.Init;
		mainInitPending := TRUE;
	ELSE
		operationType := OperatingMode.Run;
	END_IF;

	(* Timing generation *)
	(* 
	 * Uncomment if you want to make loops shorter than 10 ms.
	 * It is not recommended to go below 5 ms with the PLC.
	 * The control loop (current) of the axes is in the servo drives.
	 *)
	(* clks.systemClock := NOT clks.systemClock; *)
	clockGen(operationType := operationType);

	(*
	 * Always run internal procedures, timing generation, process inputs/outputs to ensure safe state 
	 * even in software error state, but not in case of hardware/firmware fault.
	 *)
	(* Run hardware fault detection procedures (run network and remote IO diagnostics). *)
	(* runNetworkDgs(error => ec.error);
	IF ec.error THEN
		(* Best if set by an external supervision system: init := FALSE; *)
		status := MoquiStartStatus.Idle;
		RETURN; (* Recycle until the fault condition disappears *)
	END_IF; *)

	(* Input virtualization *)
	(* inputProcessing(operationType := operationType); *)

	(* 
	 * Device config (recipe) orchestration must also run during Init because the
	 * first recipe carries the device initialization and homing parameters.
	 *)
	configMgmt(enable := ec.enable, configCompleted := mainDone,
		allConfigLoaded => allConfigLoaded, error => ec.error);
	(*
	 * Main exposes completion as a level signal; derive a one-scan event here
	 * because recipe advancement and context reset are one-shot actions.
	 *)
	mainDoneREdge(CLK := mainDone);
	IF mainDoneREdge.Q THEN
		deviceConfigContextResetRequest := TRUE;
	END_IF;

	(* Start FMS *)
	CASE status OF
	    MoquiStartStatus.Idle :
			(* Waiting for error reset from supervision *)
	        IF NOT ec.error AND ec.enable THEN
				logger(message := 'Framework started.', level := LogLevel.Info);
	            mainDone := FALSE;
				deviceConfigContextResetRequest := FALSE;
	            status := MoquiStartStatus.Run;
	        END_IF;

	    MoquiStartStatus.Run :
	        IF configMgmt.error THEN
				status := MoquiStartStatus.Error;
	        ELSIF NOT configMgmt.busy THEN
	            IF allConfigLoaded THEN
					logger(message := 'All device configs loaded. Framework idle.', level := LogLevel.Info);
					(* Auto disable waiting for new device configs from Moqui or supervision *)
	                ec.enable := FALSE;
	                status := MoquiStartStatus.Idle;
				ELSE
	                (*
	                 * Run the component FSMs sequentially.
					 * The Main component can act as a dispatcher for invoking
	                 * the system's FSM and its subsystems.
					 *
					 * The very first call after recipe load must be Init so that
					 * all device FBs consume their recipe-based init/homing params.
	                 *)
	                main(operationType := SEL(mainInitPending, OperatingMode.Run, OperatingMode.Init),
						enable := ec.enable, deviceConfigContextResetRequest := deviceConfigContextResetRequest,
						done => mainDone, error => ec.error);
					mainInitPending := FALSE;
					deviceConfigContextResetRequest := FALSE;
					IF main.error THEN status := MoquiStartStatus.Error; END_IF;
	            END_IF;
	        END_IF;
        
	    MoquiStartStatus.Error :
	        (* Retry logic *)
			IF retryOnError AND (retryCount < maxRetryCount) THEN
				(* Retry timer update *)
				IF clks.clock1s THEN
					retryTime := retryTime + 1;
				END_IF;
	
				IF (retryTime >= minRetryTime) THEN
					logger(message := 'Retrying after error ...', level := LogLevel.Warn);
					retryCount := retryCount + 1;
					retryTime := 0; (* Reset the timer *)
					autoReset := TRUE; (* Auto reset *)
				END_IF;
			END_IF;
		
	        IF reset OR autoReset THEN
	            logger(message := 'Resetting framework after error.', level := LogLevel.Warn);
	            ec.error := FALSE;
	            retryCount := 0;
	            retryTime := 0;
				mainInitPending := TRUE;
				deviceConfigContextResetRequest := FALSE;
	            status := MoquiStartStatus.Idle;
	        END_IF;
	END_CASE;

	(* Output virtualization *)
	(* outputProcessing(operationType := operationType); *)
	(* Reset the init pulse *)
	ec.init := FALSE;
	END_PROGRAM

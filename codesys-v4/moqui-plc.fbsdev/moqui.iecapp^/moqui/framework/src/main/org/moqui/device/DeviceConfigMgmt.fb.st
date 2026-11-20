(*
 * Pure recipe sequencing logic. Implement complex logic, including micro-recipe composition,
 * alternative recipes, condition-based recipes, etc., if needed.
 *
 * A failed command (Init/Load) resets the recipe manager once and stops in Error, with error kept TRUE:
 * a rising edge of reset starts again. It does not reload the recipes in a loop.
 *)
FUNCTION_BLOCK DeviceConfigMgmt
	
	VAR_INPUT
		enable : BOOL;
		continueAfterError : BOOL;
		configCompleted : BOOL; (* Config processed feedback *)
		reset : BOOL; (* Rising edge: leave Error and start again *)
	END_VAR
	VAR_OUTPUT
	    done, allConfigLoaded, busy, error : BOOL;
		errorId : DWORD;
	END_VAR
	VAR
	    status : DeviceConfigMgmtStatus := DeviceConfigMgmtStatus.Idle;
	    configCmds : DeviceConfigCmds;
	    currentConfigIndex : UINT := 0;
		(* Logger facade *)
	    logger : LoggerFacade;
		init : BOOL;
		configCompletedREdge : R_TRIG;
		resetREdge : R_TRIG;
	END_VAR

	IF NOT init THEN
		(* Logger facade init *)
		logger.enable := TRUE; logger.loggerName := MoquiConf.applicationDeviceId;
		init := TRUE;
	END_IF;

	configCompletedREdge(CLK := configCompleted);
	resetREdge(CLK := reset);

	CASE status OF
	    DeviceConfigMgmtStatus.Idle :
			done := FALSE; busy := FALSE;

	        IF enable THEN
				busy := TRUE;
				(* Setup the default config type *)
	            configCmds.configType := MoquiConf.defaultConfigType;
	            status := DeviceConfigMgmtStatus.Init;
	        END_IF;

	    DeviceConfigMgmtStatus.Init :
			allConfigLoaded := FALSE;
			configCmds(cmd := DeviceConfigCmdType.Init, error => error, errorId => errorId);

	        IF configCmds.error THEN
				status := DeviceConfigMgmtStatus.Resetting;
			ELSE
	            status := DeviceConfigMgmtStatus.Load;
	        END_IF;

	    DeviceConfigMgmtStatus.Load :
	        IF (currentConfigIndex >= configCmds.configNameListSize) THEN
	            busy := TRUE;
	            status := DeviceConfigMgmtStatus.Completed;
	        ELSE
	            configCmds.configName := configCmds.configNameList[currentConfigIndex];
	            configCmds(cmd := DeviceConfigCmdType.Load, error => error, errorId => errorId);
	            IF configCmds.error THEN
	                status := DeviceConfigMgmtStatus.Resetting;
	            ELSE
	                status := DeviceConfigMgmtStatus.WaitProcessing;
	            END_IF;
	        END_IF;

	    DeviceConfigMgmtStatus.WaitProcessing :
			done := TRUE;
			busy := FALSE;

	        IF configCompletedREdge.Q THEN
	            done := FALSE;
	            logger(message := concat(concat('Device config ', configCmds.configName), ' completed.'), level := LogLevel.Info);
	            currentConfigIndex := currentConfigIndex + 1;
	            status := DeviceConfigMgmtStatus.Load;
	        END_IF;

	    DeviceConfigMgmtStatus.Completed :
	        allConfigLoaded := TRUE;
			done := TRUE;
			busy := FALSE;
			error := FALSE;
			currentConfigIndex := 0;
	        logger(message := 'All device configs loaded.', level := LogLevel.Info);
	        status := DeviceConfigMgmtStatus.Idle;

	    DeviceConfigMgmtStatus.Resetting :
	        (* error and errorId keep the failed command's values *)
	        configCmds(cmd := DeviceConfigCmdType.Reset);
			IF NOT continueAfterError THEN
	        	currentConfigIndex := 0;
	        END_IF;
	        logger(message := 'Device config error. Waiting for a reset.', level := LogLevel.Error);
	        status := DeviceConfigMgmtStatus.Error;

	    DeviceConfigMgmtStatus.Error :
	        error := TRUE;
	        busy := FALSE;
	        done := FALSE;
	        IF resetREdge.Q THEN
	            error := FALSE;
	            errorId := 0;
	            status := DeviceConfigMgmtStatus.Idle;
	        END_IF;
	END_CASE;
	END_FUNCTION_BLOCK

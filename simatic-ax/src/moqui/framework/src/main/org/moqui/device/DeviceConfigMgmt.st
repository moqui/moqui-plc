USING System.Strings;

(*
 * Pure recipe sequencing logic. Implement complex logic, including micro-recipe composition,
 * alternative recipes, condition-based recipes, etc., if needed.
 *
 * A failed command (Init/Load) resets the recipe manager once and stops in Error, with error kept TRUE:
 * a rising edge of reset starts again. It does not reload the recipes in a loop.
 *)
FUNCTION_BLOCK DeviceConfigMgmt
	VAR_EXTERNAL CONSTANT
		applicationDeviceId : STRING;
		defaultConfigType : STRING;
	END_VAR
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
	    status : DeviceConfigMgmtStatus := DeviceConfigMgmtStatus#Idle;
	    configCmds : DeviceConfigCmds;
	    currentConfigIndex : UINT := UINT#0;
		(* Logger facade *)
	    logger : LoggerFacade;
		init : BOOL;
		configCompletedREdge : R_TRIG;
		configCmdsBusy : BOOL;
		resetREdge : R_TRIG;
	END_VAR

	IF NOT init THEN
		(* Logger facade init *)
		logger.enable := TRUE; logger.loggerName := applicationDeviceId;
		init := TRUE;
	END_IF;

	configCompletedREdge(CLK := configCompleted);
	configCmdsBusy := (configCmds.errorId = DWORD#16#7001) OR (configCmds.errorId = DWORD#16#7002);
	resetREdge(CLK := reset);

	CASE status OF
	    DeviceConfigMgmtStatus#Idle :
			done := FALSE; busy := FALSE;

	        IF enable THEN
				busy := TRUE;
				(* Setup the default config type *)
	            configCmds.configType := defaultConfigType;
	            status := DeviceConfigMgmtStatus#Init;
	        END_IF;

	    DeviceConfigMgmtStatus#Init :
			allConfigLoaded := FALSE;
			busy := TRUE;
			configCmds(cmd := DeviceConfigCmdType#Init, error => error, errorId => errorId);

	        IF configCmds.error THEN
				status := DeviceConfigMgmtStatus#Resetting;
			ELSIF configCmdsBusy THEN
				status := DeviceConfigMgmtStatus#Init;
			ELSE
	            status := DeviceConfigMgmtStatus#Load;
	        END_IF;

	    DeviceConfigMgmtStatus#Load :
			busy := TRUE;
	        IF currentConfigIndex >= configCmds.configNameListSize THEN
	            status := DeviceConfigMgmtStatus#Completed;
	        ELSE
	            configCmds.configName := configCmds.configNameList[currentConfigIndex];
	            configCmds(cmd := DeviceConfigCmdType#Load, error => error, errorId => errorId);
	            IF configCmds.error THEN
	                status := DeviceConfigMgmtStatus#Resetting;
	            ELSIF configCmdsBusy THEN
	                status := DeviceConfigMgmtStatus#WaitLoad;
	            ELSE
	                status := DeviceConfigMgmtStatus#WaitProcessing;
	            END_IF;
	        END_IF;

	    DeviceConfigMgmtStatus#WaitLoad :
			done := FALSE;
			busy := TRUE;
	        configCmds.configName := configCmds.configNameList[currentConfigIndex];
	        configCmds(cmd := DeviceConfigCmdType#Load, error => error, errorId => errorId);
	        IF configCmds.error THEN
	            status := DeviceConfigMgmtStatus#Resetting;
	        ELSIF configCmdsBusy THEN
	            status := DeviceConfigMgmtStatus#WaitLoad;
	        ELSE
	            status := DeviceConfigMgmtStatus#WaitProcessing;
	        END_IF;

	    DeviceConfigMgmtStatus#WaitProcessing :
			done := TRUE;
			busy := FALSE;

	        IF configCompletedREdge.Q THEN
	            done := FALSE;
	            logger(message := Concat(Concat('Device config ', configCmds.configName), ' completed.'), level := LogLevel#Info);
	            currentConfigIndex := currentConfigIndex + UINT#1;
	            status := DeviceConfigMgmtStatus#Load;
	        END_IF;

	    DeviceConfigMgmtStatus#Completed :
	        allConfigLoaded := TRUE;
			done := TRUE;
			busy := FALSE;
			error := FALSE;
			currentConfigIndex := UINT#0;
	        logger(message := 'All device configs loaded.', level := LogLevel#Info);
	        status := DeviceConfigMgmtStatus#Idle;

	    DeviceConfigMgmtStatus#Resetting :
	        (* error and errorId keep the failed command's values *)
	        configCmds(cmd := DeviceConfigCmdType#Reset);
			IF NOT continueAfterError THEN
	        	currentConfigIndex := UINT#0;
	        END_IF;
	        logger(message := 'Device config error. Waiting for a reset.', level := LogLevel#Error);
	        status := DeviceConfigMgmtStatus#Error;

	    DeviceConfigMgmtStatus#Error :
	        error := TRUE;
	        busy := FALSE;
	        done := FALSE;
	        IF resetREdge.Q THEN
	            error := FALSE;
	            errorId := DWORD#16#0000;
	            status := DeviceConfigMgmtStatus#Idle;
	        END_IF;
	END_CASE;
	END_FUNCTION_BLOCK

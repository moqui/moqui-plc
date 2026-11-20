(* Run network diagnostics on the Ethernet adapter and IO modules *)
FUNCTION_BLOCK NetworkDiagnostics
	VAR_EXTERNAL CONSTANT
		applicationDeviceId : STRING;
	END_VAR
	VAR_EXTERNAL
		fieldbus : FieldbusProtocol;
	END_VAR
	VAR_OUTPUT
		error: BOOL;
	END_VAR
	VAR
		(* Logger facade *)
		logger : LoggerFacade;
		module : DED.IDevice;
		moduleInfo : DED.DEVICE_INFO;
		moduleName : STRING;
		moduleStatus : DED.DEVICE_STATE;
		moduleError : DED.ERROR;
		diagnosisInfoAvailable : BOOL;
	    diagnosisInfoBuffer : STRING; 
	    dataCount : DED.CAA.SIZE;
		diagnoseIoModule : RemoteIoModuleDiagnostics;
		moduleDiagnosisError : BOOL;
		anyError : BOOL;
		(* Error of the previous call, so that details are logged when the diagnostics turn to error *)
		errorOld : BOOL;
		i: INT;
		init : BOOL;
	END_VAR
	VAR CONSTANT
		(* Guard against a malformed device tree *)
		MAX_MODULES : INT := 256;
	END_VAR

	error := TRUE;

	IF NOT init THEN
		(* Logger facade init *)
		logger.enable := TRUE; logger.loggerName := applicationDeviceId;
		init := TRUE;
	END_IF;

	(* 
	 * CODESYS includes an OPC UA Server that exposes the PLC variables for external clients.
	 * Typically, you do not detect the server's "failure" directly in user logic,
	 * because the server is part of the CODESYS runtime.
	 *)

	(*
	 * To enable/disable the ethernet adapter or other devices, use the following reconfigure command: 
	 *     Ethernet.Enable := TRUE/FALSE;
	 *     reconfigure(xExecute := TRUE, itfNode := Ethernet);
	*)
 
	(* For applications without remote IO modules or with IO modules integrated into the PLC rack. *)
	IF NOT ethernet.Enable THEN
		logger(message := 'The Ethernet adapter is disabled.', level := LogLevel.DEBUG);
		error := FALSE;
		RETURN;
	END_IF;
	IF ethernet.ChildNodeCount = 0 THEN
		logger(message := 'No child devices under the Ethernet adapter. Disable the Ethernet adapter!', level := LogLevel.Warn);
	END_IF;
	IF ethernet.State = IODrvEthernet.EthernetState.ERROR THEN
		logger(message := 'Ethernet adapter in error state.', level := LogLevel.ERROR);
		RETURN;
	END_IF;
	IF ethernet.State = IODrvEthernet.EthernetState.NOT_CONFIGURED THEN
		logger(message := 'Ethernet adapter not configured.', level := LogLevel.ERROR);
		RETURN;
	END_IF;
	IF ethernet.State = IODrvEthernet.EthernetState.SET_IP_ERROR THEN
		logger(message := 'Invalid IP address configured for the Ethernet adapter.', level := LogLevel.ERROR);
		RETURN;
	END_IF;
	IF ethernet.State = IODrvEthernet.EthernetState.DISCONNECTED THEN
		logger(message := 'Ethernet adapter disconnected.', level := LogLevel.ERROR);
		RETURN;
	END_IF;

	(* 
	 * Avoid checking software subsystems of the network stack (e.g. Modbus TCP Client component).
	 * Check only the physical remote devices, starting from the first one: every module is checked,
	 * and an empty node ends the list. Details are logged when the diagnostics turn to error.
	 *)
	anyError := FALSE;
	module := DED.INode_TO_IDevice(ethernet.FirstChildNode.FirstChildNode);
	i := 0;
	WHILE (module <> 0) AND (i < MAX_MODULES) DO
		i := i + 1;
		module.GetDeviceInfo(deiInfo := moduleInfo);
		moduleName := DED.GetDeviceNameString(module);

		IF module.Enable THEN
			moduleStatus := module.GetDeviceState(xDiagnosisinfoAvailable => diagnosisInfoAvailable, eError => moduleError);
			IF moduleStatus = DED.DEVICE_STATE.ERROR THEN
				anyError := TRUE;
				IF NOT errorOld THEN
					logger(message := concat(concat(concat(concat('The ', moduleName), ' IO module is in error state.'), ' Error code: '),
						TO_STRING(moduleError)), level := LogLevel.ERROR);
					logger(message := concat(concat(concat(concat(concat('Module info: Type ', TO_STRING(moduleInfo.eType)), ' - Instance number '),
						TO_STRING(moduleInfo.idInstance)), ' - Unique ID '), TO_STRING(moduleInfo.idSystem)), level := LogLevel.ERROR);
					IF diagnosisInfoAvailable THEN
						(* The diagnosis data is copied into diagnosisInfoBuffer, then logged as text *)
						diagnosisInfoBuffer := '';
						moduleError := module.GetDeviceDiagnosisInfo(pData := ADR(diagnosisInfoBuffer),
							szSize := SIZEOF(diagnosisInfoBuffer) - 1, szCount => dataCount);
						logger(message := concat('Diagnosis error code: ', TO_STRING(moduleError)), level := LogLevel.ERROR);
						logger(message := concat('Diagnosis data: ', diagnosisInfoBuffer), level := LogLevel.ERROR);
					END_IF;
				END_IF;
			ELSE
				(* 
			     * Check the remote IO module registers for detecting any errors, if needed.
				 * Otherwise, comment out the following code.
			     *)
				diagnoseIoModule(moduleName := moduleName, error => moduleDiagnosisError, diagnosisInfo => diagnosisInfoBuffer);
				IF moduleDiagnosisError THEN
					anyError := TRUE;
					IF NOT errorOld THEN
						logger(message := concat(concat('The remote IO module ', moduleName), ' is connected but has errors.'), level := LogLevel.ERROR);
						logger(message := concat('Error stack: ', diagnosisInfoBuffer), level := LogLevel.ERROR);
					END_IF;
				END_IF;
			END_IF;
		END_IF;

		module := DED.INode_TO_IDevice(module.NextSiblingNode);
	END_WHILE;

	error := anyError;
	IF errorOld AND NOT error THEN logger(message := 'Network diagnostics: no errors.', level := LogLevel.Info); END_IF;
	errorOld := error;
	END_FUNCTION_BLOCK

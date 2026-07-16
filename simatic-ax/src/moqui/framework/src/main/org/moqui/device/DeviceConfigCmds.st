USING Siemens.Simatic.S71500.FileAccess;
USING System.Strings;

FUNCTION_BLOCK DeviceConfigCmds
	VAR_EXTERNAL CONSTANT
		applicationDeviceId : STRING;
		DEVICE_CONFIG_LIST_MAX_SIZE : UINT;
		defaultConfigType : STRING;
		deviceConfigStoragePath : STRING;
	END_VAR
	VAR_EXTERNAL
		dev : DeviceFacade;
	END_VAR
	VAR_INPUT
	    configType : STRING := defaultConfigType; (* If empty, set default device config type *)
		(*
	     * The default file name of a recipe is: <configName>.<configType>.<extension>
	     * Device config ID or name used by the commands.
	     *)
	    configName : STRING := '';
	    cmd : DeviceConfigCmdType := DeviceConfigCmdType#Load;
	END_VAR
	VAR_OUTPUT
		(* Device config list *)
		configNameList : ARRAY[0..DEVICE_CONFIG_LIST_MAX_SIZE] OF STRING;
		configNameListSize : UINT;
		error : BOOL;
		errorId : DWORD; (* 16#5000 : InvalidArgs *)
	END_VAR
	VAR
		indexReader : ReadFile;
		recipeReader : ReadFile;
		indexBuffer : ARRAY[0..4095] OF BYTE;
		recipeBuffer : ARRAY[0..16383] OF BYTE;
		configFileNameList : ARRAY[0..DEVICE_CONFIG_LIST_MAX_SIZE] OF STRING;
		activeRecipeFileName : STRING;
		lastConfigName : STRING;
		lastCmd : DeviceConfigCmdType := DeviceConfigCmdType#Reset;
		indexReaderIssued : BOOL;
		recipeReaderIssued : BOOL;
		indexLoaded : BOOL;
		recipeLoaded : BOOL;
		(* Logger facade *)
		logger : LoggerFacade;
	END_VAR
	VAR_TEMP
		listIndex : UINT;
		parseIndex : DINT;
		lineStart : DINT;
		lineEnd : DINT;
		lineLength : DINT;
		tempLength : INT;
		firstSeparator : INT;
		secondSeparator : INT;
		secondSeparatorRelative : INT;
		paramId : DINT;
		componentIndex : DINT;
		commandChanged : BOOL;
		lineText : STRING[254];
		fieldA : STRING[120];
		fieldB : STRING[120];
		fieldC : STRING[120];
		sortTempName : STRING;
		sortTempFileName : STRING;
		sortSwapped : BOOL;
	END_VAR

	VAR CONSTANT
		ERR_INVALID_ARGS : DWORD := DWORD#16#5000;
		ERR_READ_INDEX : DWORD := DWORD#16#5001;
		ERR_PARSE_INDEX : DWORD := DWORD#16#5002;
		ERR_CONFIG_NOT_FOUND : DWORD := DWORD#16#5003;
		ERR_READ_RECIPE : DWORD := DWORD#16#5004;
		ERR_PARSE_RECIPE : DWORD := DWORD#16#5005;
		ERR_NOT_SUPPORTED : DWORD := DWORD#16#5006;
		INDEX_FILE_PATH : STRING := 'UserFiles/index.csv';
		USER_FILES_PREFIX : STRING := 'UserFiles/';
	END_VAR

	(* Logger facade init *)
	logger.enable := TRUE;
	logger.loggerName := applicationDeviceId;

	commandChanged := (cmd <> lastCmd) OR ((cmd = DeviceConfigCmdType#Load) AND (configName <> lastConfigName));
	IF commandChanged THEN
		indexReaderIssued := FALSE;
		recipeReaderIssued := FALSE;
		indexLoaded := FALSE;
		recipeLoaded := FALSE;
		activeRecipeFileName := '';
		lastCmd := cmd;
		lastConfigName := configName;
	END_IF;

	(* Args validation *)
	IF (configType = '') OR ((cmd <> DeviceConfigCmdType#Init) AND (cmd <> DeviceConfigCmdType#Reset) AND (configName = '')) THEN
		logger(message := 'Invalid arguments.', level := LogLevel#Error);
		error := TRUE;
		errorId := ERR_INVALID_ARGS;
		RETURN;
	END_IF;

	CASE cmd OF
		DeviceConfigCmdType#Init :
			IF commandChanged THEN
				logger(message := 'Loading device config list.');
				listIndex := UINT#0;
				WHILE listIndex <= DEVICE_CONFIG_LIST_MAX_SIZE DO
					configNameList[listIndex] := '';
					configFileNameList[listIndex] := '';
					listIndex := listIndex + UINT#1;
				END_WHILE;
				configNameListSize := UINT#0;
			END_IF;

			indexReader(
				execute := NOT indexReaderIssued AND NOT indexLoaded,
				path := INDEX_FILE_PATH,
				offset := UDINT#0,
				length := UDINT#4096,
				data := indexBuffer
			);
			IF NOT indexReaderIssued AND NOT indexLoaded THEN
				indexReaderIssued := TRUE;
			END_IF;

			IF indexReader.error THEN
				logger(message := 'Error loading device config list from file system.', level := LogLevel#Error);
				error := TRUE;
				errorId := ERR_READ_INDEX;
				RETURN;
			END_IF;

			IF indexReader.busy AND NOT indexReader.done THEN
				error := FALSE;
				errorId := TO_DWORD(indexReader.status);
				RETURN;
			END_IF;

			IF indexReader.done AND NOT indexLoaded THEN
				indexLoaded := TRUE;
				lineStart := DINT#0;

				WHILE lineStart < TO_DINT(indexReader.resultLength) DO
					WHILE (lineStart < TO_DINT(indexReader.resultLength))
							AND ((indexBuffer[lineStart] = BYTE#10) OR (indexBuffer[lineStart] = BYTE#13)) DO
						lineStart := lineStart + DINT#1;
					END_WHILE;

					IF lineStart >= TO_DINT(indexReader.resultLength) THEN
						EXIT;
					END_IF;

					lineEnd := lineStart;
					WHILE (lineEnd < TO_DINT(indexReader.resultLength))
							AND (indexBuffer[lineEnd] <> BYTE#10)
							AND (indexBuffer[lineEnd] <> BYTE#13) DO
						lineEnd := lineEnd + DINT#1;
					END_WHILE;

					lineLength := lineEnd - lineStart;
					IF lineLength > DINT#0 THEN
						CharsToString(chars := indexBuffer, startPosition := lineStart, length := TO_UINT(lineLength), result => lineText);
						IF lineText <> 'name,configType,fileName' THEN
							firstSeparator := PositionOf(lineText, ',');
							IF firstSeparator = INT#0 THEN
								error := TRUE;
								errorId := ERR_PARSE_INDEX;
								logger(message := 'Invalid index.csv line.', level := LogLevel#Error);
								RETURN;
							END_IF;

							fieldA := Substring(lineText, INT#1, firstSeparator - INT#1);
							tempLength := LengthOf(lineText);
							fieldB := Substring(lineText, firstSeparator + INT#1, tempLength - firstSeparator);
							secondSeparatorRelative := PositionOf(fieldB, ',');
							IF secondSeparatorRelative = INT#0 THEN
								error := TRUE;
								errorId := ERR_PARSE_INDEX;
								logger(message := 'Invalid index.csv line.', level := LogLevel#Error);
								RETURN;
							END_IF;

							fieldC := Substring(fieldB, secondSeparatorRelative + INT#1, LengthOf(fieldB) - secondSeparatorRelative);
							fieldB := Substring(fieldB, INT#1, secondSeparatorRelative - INT#1);

							IF fieldB = configType THEN
								IF configNameListSize <= DEVICE_CONFIG_LIST_MAX_SIZE THEN
									configNameList[configNameListSize] := fieldA;
									configFileNameList[configNameListSize] := fieldC;
									configNameListSize := configNameListSize + UINT#1;
								END_IF;
							END_IF;
						END_IF;
					END_IF;

					lineStart := lineEnd + DINT#1;
				END_WHILE;

				IF configNameListSize > UINT#1 THEN
					REPEAT
						sortSwapped := FALSE;
						parseIndex := DINT#0;
						WHILE parseIndex < TO_DINT(configNameListSize - UINT#1) DO
							IF configNameList[TO_UINT(parseIndex)] > configNameList[TO_UINT(parseIndex + DINT#1)] THEN
								sortTempName := configNameList[TO_UINT(parseIndex)];
								configNameList[TO_UINT(parseIndex)] := configNameList[TO_UINT(parseIndex + DINT#1)];
								configNameList[TO_UINT(parseIndex + DINT#1)] := sortTempName;

								sortTempFileName := configFileNameList[TO_UINT(parseIndex)];
								configFileNameList[TO_UINT(parseIndex)] := configFileNameList[TO_UINT(parseIndex + DINT#1)];
								configFileNameList[TO_UINT(parseIndex + DINT#1)] := sortTempFileName;
								sortSwapped := TRUE;
							END_IF;
							parseIndex := parseIndex + DINT#1;
						END_WHILE;
					UNTIL NOT sortSwapped
					END_REPEAT;
				END_IF;
			END_IF;

			error := FALSE;
			errorId := DWORD#16#0000;

		DeviceConfigCmdType#Load :
			activeRecipeFileName := '';
			parseIndex := DINT#0;
			WHILE parseIndex < TO_DINT(configNameListSize) DO
				IF configNameList[TO_UINT(parseIndex)] = configName THEN
					activeRecipeFileName := configFileNameList[TO_UINT(parseIndex)];
				END_IF;
				parseIndex := parseIndex + DINT#1;
			END_WHILE;

			IF activeRecipeFileName = '' THEN
				error := TRUE;
				errorId := ERR_CONFIG_NOT_FOUND;
				logger(message := 'Device config not found in index.', level := LogLevel#Error);
				RETURN;
			END_IF;

			recipeReader(
				execute := NOT recipeReaderIssued AND NOT recipeLoaded,
				path := Concat(USER_FILES_PREFIX, activeRecipeFileName),
				offset := UDINT#0,
				length := UDINT#16384,
				data := recipeBuffer
			);
			IF NOT recipeReaderIssued AND NOT recipeLoaded THEN
				recipeReaderIssued := TRUE;
			END_IF;

			IF recipeReader.error THEN
				logger(message := 'Error loading device config recipe file.', level := LogLevel#Error);
				error := TRUE;
				errorId := ERR_READ_RECIPE;
				RETURN;
			END_IF;

			IF recipeReader.busy AND NOT recipeReader.done THEN
				error := FALSE;
				errorId := TO_DWORD(recipeReader.status);
				RETURN;
			END_IF;

			IF recipeReader.done AND NOT recipeLoaded THEN
				recipeLoaded := TRUE;
				lineStart := DINT#0;

				WHILE lineStart < TO_DINT(recipeReader.resultLength) DO
					WHILE (lineStart < TO_DINT(recipeReader.resultLength))
							AND ((recipeBuffer[lineStart] = BYTE#10) OR (recipeBuffer[lineStart] = BYTE#13)) DO
						lineStart := lineStart + DINT#1;
					END_WHILE;

					IF lineStart >= TO_DINT(recipeReader.resultLength) THEN
						EXIT;
					END_IF;

					lineEnd := lineStart;
					WHILE (lineEnd < TO_DINT(recipeReader.resultLength))
							AND (recipeBuffer[lineEnd] <> BYTE#10)
							AND (recipeBuffer[lineEnd] <> BYTE#13) DO
						lineEnd := lineEnd + DINT#1;
					END_WHILE;

					lineLength := lineEnd - lineStart;
					IF lineLength > DINT#0 THEN
						CharsToString(chars := recipeBuffer, startPosition := lineStart, length := TO_UINT(lineLength), result => lineText);
						firstSeparator := PositionOf(lineText, ';');
						IF firstSeparator = INT#0 THEN
							error := TRUE;
							errorId := ERR_PARSE_RECIPE;
							logger(message := 'Invalid AX recipe line.', level := LogLevel#Error);
							RETURN;
						END_IF;

						fieldA := Substring(lineText, INT#1, firstSeparator - INT#1);
						tempLength := LengthOf(lineText);
						fieldB := Substring(lineText, firstSeparator + INT#1, tempLength - firstSeparator);
						secondSeparatorRelative := PositionOf(fieldB, ';');
						IF secondSeparatorRelative = INT#0 THEN
							error := TRUE;
							errorId := ERR_PARSE_RECIPE;
							logger(message := 'Invalid AX recipe line.', level := LogLevel#Error);
							RETURN;
						END_IF;

						fieldC := Substring(fieldB, secondSeparatorRelative + INT#1, LengthOf(fieldB) - secondSeparatorRelative);
						fieldB := Substring(fieldB, INT#1, secondSeparatorRelative - INT#1);
						paramId := ParseRecipeDInt(fieldA);

						CASE paramId OF
							DINT#1 : dev.tempSetpoint := ParseRecipeReal(fieldC);
							DINT#2 : dev.tempHysteresis := ParseRecipeReal(fieldC);
							DINT#3 : dev.tempMin := ParseRecipeReal(fieldC);
							DINT#4 : dev.tempMax := ParseRecipeReal(fieldC);
							DINT#5 : dev.rhSetpoint := ParseRecipeReal(fieldC);
							DINT#6 : dev.rhHysteresis := ParseRecipeReal(fieldC);
							DINT#7 : dev.rhMin := ParseRecipeReal(fieldC);
							DINT#8 : dev.rhMax := ParseRecipeReal(fieldC);
							DINT#9 : dev.airDistributionEnabled := (fieldC = 'TRUE');
							DINT#10 : dev.setPointTimeHigh := TO_UINT(ParseRecipeDInt(fieldC));
							DINT#11 : dev.setPointTimeLow := TO_UINT(ParseRecipeDInt(fieldC));
							DINT#14 : dev.ductTempMin := ParseRecipeReal(fieldC);
							DINT#15 : dev.ductTempMax := ParseRecipeReal(fieldC);
							DINT#16 : dev.ductRhMax := ParseRecipeReal(fieldC);
							DINT#17 : dev.rhControlEnabled := (fieldC = 'TRUE');
							DINT#18 : dev.rhControlOnly := (fieldC = 'TRUE');
							DINT#20 : dev.airMixingEnabled := (fieldC = 'TRUE');
							DINT#21 : dev.estimatedRuntime := TO_UDINT(ParseRecipeDInt(fieldC));
							DINT#22 : dev.minRuntime := TO_UDINT(ParseRecipeDInt(fieldC));
							DINT#23 : dev.estimatedBreakDuration := TO_UDINT(ParseRecipeDInt(fieldC));
							DINT#24 : dev.minBreakDuration := TO_UDINT(ParseRecipeDInt(fieldC));
							DINT#25 : dev.processEstimatedDuration := TO_UDINT(ParseRecipeDInt(fieldC));
							DINT#26 : dev.processMinDuration := TO_UDINT(ParseRecipeDInt(fieldC));
							DINT#27 : dev.airFlowRef := ParseRecipeReal(fieldC);
							DINT#28 : dev.ahuFanSpeedSetpoint := ParseRecipeReal(fieldC);
							DINT#29 : dev.tempFeedback := ParseRecipeReal(fieldC);
							DINT#30 : dev.rhFeedback := ParseRecipeReal(fieldC);
							DINT#33 : dev.ductTempFeedback := ParseRecipeReal(fieldC);
							DINT#34 : dev.ductRhFeedback := ParseRecipeReal(fieldC);
							DINT#35 : dev.coldGlycolPump.actuatorId := fieldC;
							DINT#36 : dev.coldGlycolPump.actuatorName := fieldC;
							DINT#37 :
								CASE ParseRecipeDInt(fieldC) OF
									DINT#0 : dev.coldGlycolPump.actuationType := ActuatorActuationType#SingleActuation;
									DINT#1 : dev.coldGlycolPump.actuationType := ActuatorActuationType#DoubleActuation;
									DINT#2 : dev.coldGlycolPump.actuationType := ActuatorActuationType#DoubleActuationNoRetain;
								END_CASE;
							DINT#38 :
								CASE ParseRecipeDInt(fieldC) OF
									DINT#0 : dev.coldGlycolPump.feedbackType := ActuatorFeedbackType#WithoutFeedback;
									DINT#1 : dev.coldGlycolPump.feedbackType := ActuatorFeedbackType#SingleDisableFeedback;
									DINT#2 : dev.coldGlycolPump.feedbackType := ActuatorFeedbackType#SingleEnableFeedback;
									DINT#3 : dev.coldGlycolPump.feedbackType := ActuatorFeedbackType#DoubleFeedback;
								END_CASE;
							DINT#39 :
								CASE ParseRecipeDInt(fieldC) OF
									DINT#0 : dev.coldGlycolPump.model := ActuatorModel#ABBACH580;
									DINT#1 : dev.coldGlycolPump.model := ActuatorModel#CTM700;
									DINT#2 : dev.coldGlycolPump.model := ActuatorModel#DanfossFC102;
									DINT#3 : dev.coldGlycolPump.model := ActuatorModel#ABBPSTX;
								END_CASE;
							DINT#40 : dev.coldGlycolPump.enableTime := TO_UINT(ParseRecipeDInt(fieldC));
							DINT#41 : dev.coldGlycolPump.disableTime := TO_UINT(ParseRecipeDInt(fieldC));
							DINT#42 : dev.coldGlycolPump.diagnosticsEnable := (fieldC = 'TRUE');
							DINT#43 : dev.hotGlycolPump.actuatorId := fieldC;
							DINT#44 : dev.hotGlycolPump.actuatorName := fieldC;
							DINT#45 :
								CASE ParseRecipeDInt(fieldC) OF
									DINT#0 : dev.hotGlycolPump.actuationType := ActuatorActuationType#SingleActuation;
									DINT#1 : dev.hotGlycolPump.actuationType := ActuatorActuationType#DoubleActuation;
									DINT#2 : dev.hotGlycolPump.actuationType := ActuatorActuationType#DoubleActuationNoRetain;
								END_CASE;
							DINT#46 :
								CASE ParseRecipeDInt(fieldC) OF
									DINT#0 : dev.hotGlycolPump.feedbackType := ActuatorFeedbackType#WithoutFeedback;
									DINT#1 : dev.hotGlycolPump.feedbackType := ActuatorFeedbackType#SingleDisableFeedback;
									DINT#2 : dev.hotGlycolPump.feedbackType := ActuatorFeedbackType#SingleEnableFeedback;
									DINT#3 : dev.hotGlycolPump.feedbackType := ActuatorFeedbackType#DoubleFeedback;
								END_CASE;
							DINT#47 :
								CASE ParseRecipeDInt(fieldC) OF
									DINT#0 : dev.hotGlycolPump.model := ActuatorModel#ABBACH580;
									DINT#1 : dev.hotGlycolPump.model := ActuatorModel#CTM700;
									DINT#2 : dev.hotGlycolPump.model := ActuatorModel#DanfossFC102;
									DINT#3 : dev.hotGlycolPump.model := ActuatorModel#ABBPSTX;
								END_CASE;
							DINT#48 : dev.hotGlycolPump.enableTime := TO_UINT(ParseRecipeDInt(fieldC));
							DINT#49 : dev.hotGlycolPump.disableTime := TO_UINT(ParseRecipeDInt(fieldC));
							DINT#50 : dev.hotGlycolPump.diagnosticsEnable := (fieldC = 'TRUE');
							DINT#51 : dev.airFlow.actuatorId := fieldC;
							DINT#52 : dev.airFlow.actuatorName := fieldC;
							DINT#53 :
								CASE ParseRecipeDInt(fieldC) OF
									DINT#0 : dev.airFlow.actuationType := ActuatorActuationType#SingleActuation;
									DINT#1 : dev.airFlow.actuationType := ActuatorActuationType#DoubleActuation;
									DINT#2 : dev.airFlow.actuationType := ActuatorActuationType#DoubleActuationNoRetain;
								END_CASE;
							DINT#54 :
								CASE ParseRecipeDInt(fieldC) OF
									DINT#0 : dev.airFlow.feedbackType := ActuatorFeedbackType#WithoutFeedback;
									DINT#1 : dev.airFlow.feedbackType := ActuatorFeedbackType#SingleDisableFeedback;
									DINT#2 : dev.airFlow.feedbackType := ActuatorFeedbackType#SingleEnableFeedback;
									DINT#3 : dev.airFlow.feedbackType := ActuatorFeedbackType#DoubleFeedback;
								END_CASE;
							DINT#55 :
								CASE ParseRecipeDInt(fieldC) OF
									DINT#0 : dev.airFlow.model := ActuatorModel#ABBACH580;
									DINT#1 : dev.airFlow.model := ActuatorModel#CTM700;
									DINT#2 : dev.airFlow.model := ActuatorModel#DanfossFC102;
									DINT#3 : dev.airFlow.model := ActuatorModel#ABBPSTX;
								END_CASE;
							DINT#56 : dev.airFlow.enableTime := TO_UINT(ParseRecipeDInt(fieldC));
							DINT#57 : dev.airFlow.disableTime := TO_UINT(ParseRecipeDInt(fieldC));
							DINT#58 : dev.airFlow.diagnosticsEnable := (fieldC = 'TRUE');
							DINT#59 : dev.coldGlycolValve.controlSystemId := fieldC;
							DINT#60 : dev.coldGlycolValve.controlSystemName := fieldC;
							DINT#61 : dev.coldGlycolValve.gain := ParseRecipeReal(fieldC);
							DINT#62 : dev.coldGlycolValve.integrationTime := ParseRecipeReal(fieldC);
							DINT#63 : dev.coldGlycolValve.derivationTime := ParseRecipeReal(fieldC);
							DINT#64 : dev.coldGlycolValve.setpointMin := ParseRecipeReal(fieldC);
							DINT#65 : dev.coldGlycolValve.setpointMax := ParseRecipeReal(fieldC);
							DINT#66 : dev.coldGlycolValve.outputMin := ParseRecipeReal(fieldC);
							DINT#67 : dev.coldGlycolValve.outputMax := ParseRecipeReal(fieldC);
							DINT#68 : dev.coldGlycolValve.atSetpointHysteresis := ParseRecipeReal(fieldC);
							DINT#69 : dev.coldGlycolValve.tickTime := ParseRecipeTime(fieldC);
							DINT#70 : dev.hotGlycolValve.controlSystemId := fieldC;
							DINT#71 : dev.hotGlycolValve.controlSystemName := fieldC;
							DINT#72 : dev.hotGlycolValve.gain := ParseRecipeReal(fieldC);
							DINT#73 : dev.hotGlycolValve.integrationTime := ParseRecipeReal(fieldC);
							DINT#74 : dev.hotGlycolValve.derivationTime := ParseRecipeReal(fieldC);
							DINT#75 : dev.hotGlycolValve.setpointMin := ParseRecipeReal(fieldC);
							DINT#76 : dev.hotGlycolValve.setpointMax := ParseRecipeReal(fieldC);
							DINT#77 : dev.hotGlycolValve.outputMin := ParseRecipeReal(fieldC);
							DINT#78 : dev.hotGlycolValve.outputMax := ParseRecipeReal(fieldC);
							DINT#79 : dev.hotGlycolValve.atSetpointHysteresis := ParseRecipeReal(fieldC);
							DINT#80 : dev.hotGlycolValve.tickTime := ParseRecipeTime(fieldC);
							DINT#81 : dev.ahuFan.controlSystemId := fieldC;
							DINT#82 : dev.ahuFan.controlSystemName := fieldC;
							DINT#83 : dev.ahuFan.gain := ParseRecipeReal(fieldC);
							DINT#84 : dev.ahuFan.integrationTime := ParseRecipeReal(fieldC);
							DINT#85 : dev.ahuFan.derivationTime := ParseRecipeReal(fieldC);
							DINT#86 : dev.ahuFan.setpointMin := ParseRecipeReal(fieldC);
							DINT#87 : dev.ahuFan.setpointMax := ParseRecipeReal(fieldC);
							DINT#88 : dev.ahuFan.outputMin := ParseRecipeReal(fieldC);
							DINT#89 : dev.ahuFan.outputMax := ParseRecipeReal(fieldC);
							DINT#90 : dev.ahuFan.atSetpointHysteresis := ParseRecipeReal(fieldC);
							DINT#91 : dev.ahuFan.tickTime := ParseRecipeTime(fieldC);
						END_CASE;
					END_IF;

					lineStart := lineEnd + DINT#1;
				END_WHILE;

				logger(message := Concat(Concat(Concat('Loaded device config ', configName), ' of type '), configType));
			END_IF;

			error := FALSE;
			errorId := DWORD#16#0000;

	    DeviceConfigCmdType#Create :
			error := TRUE;
			errorId := ERR_NOT_SUPPORTED;
			logger(message := 'Create is not supported in AX runtime.', level := LogLevel#Error);

	    DeviceConfigCmdType#Save :
	        error := TRUE;
	        errorId := ERR_NOT_SUPPORTED;
			logger(message := 'Save is not supported in AX runtime.', level := LogLevel#Error);

	    DeviceConfigCmdType#Delete :
	        error := TRUE;
			errorId := ERR_NOT_SUPPORTED;
			logger(message := 'Delete is not supported in AX runtime.', level := LogLevel#Error);
		
		DeviceConfigCmdType#Reset :
			logger(message := 'Resetting device config list.');
			listIndex := UINT#0;
			WHILE listIndex <= DEVICE_CONFIG_LIST_MAX_SIZE DO
				configNameList[listIndex] := '';
				configFileNameList[listIndex] := '';
				listIndex := listIndex + UINT#1;
			END_WHILE;
			configNameListSize := UINT#0;
			indexReaderIssued := FALSE;
			recipeReaderIssued := FALSE;
			indexLoaded := FALSE;
			recipeLoaded := FALSE;
			activeRecipeFileName := '';
			error := FALSE;
			errorId := DWORD#16#0000;
	END_CASE;
END_FUNCTION_BLOCK

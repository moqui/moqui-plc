(* 
 * Logger with local circular buffer and duplicate suppression. 
 * Designed for central orchestration by a global LogAppender.
 *)
FUNCTION_BLOCK LoggerFacade
	
	(* Log event data *)
	VAR_INPUT
	    (* Trigger for logging a new event *)
	    enable : BOOL;
		(* 
	     * Unique identifier for the log event.
	     * If empty a UUID will be generated internally.
	     *)
	    logEventId : STRING := '';
	    loggerName : STRING;
	    level : LogLevel := MoquiConf.defaultLogLevel;
		marker : LogMarker := LogMarker.Diagnostics;
		source : STRING;
	    payloadType : LogPayloadType := LogPayloadType.Text;
		message : STRING;
	    enumValue : UINT;
	    numericValue : LREAL;
		(* contextData : STRING; (* Uncomment if needed *) *)
	END_VAR
	(* Configuration parameters *)
	VAR_INPUT
		(* Duplicate suppression for log compression *)
		suppressDuplicates : BOOL := MoquiConf.defaultLogSuppressDuplicates;
	    (* Duplicate suppression window *)
	    suppressDuration : TIME := MoquiConf.defaultLogSuppressDuration;
	END_VAR
	VAR_OUTPUT
		done, error : BOOL;
	END_VAR
	VAR
		(* Local log ring buffer *)
	    logBuffer : LogRingBuffer;
	    init : BOOL := FALSE;
	    isDuplicate : BOOL;
	    now : DATE_AND_TIME;
	    lastLogEvent : LogEvent;
		(* Log event ID generator *)
	    timestamp : SysTimeRtc.SYSTIME;
	    uuid : STRING(40);
	END_VAR

	(* Register once into the log appender source list *)
	IF NOT init THEN
	    IF ec.logSourceListSize < MoquiConf.LOG_SOURCE_LIST_MAX_SIZE THEN
	        ec.logSourceListSize := ec.logSourceListSize + 1;
	        ec.logSourceList[ec.logSourceListSize].logRef REF= logBuffer;
	    ELSE
	        error := TRUE;
	    END_IF;

	    init := TRUE;
	END_IF;

	IF NOT enable THEN RETURN; END_IF;

	now := nowTimestamp();
	isDuplicate := FALSE;

	(* Compression logic (duplicate suppression) *)
	IF suppressDuplicates AND (payloadType = lastLogEvent.payloadType)
	        AND (loggerName = lastLogEvent.loggerName)
			AND (source = lastLogEvent.source) THEN
		CASE payloadType OF
			LogPayloadType.Text: isDuplicate := (message = lastLogEvent.payload.message);
			LogPayloadType.Enum: isDuplicate := (enumValue = lastLogEvent.payload.enumValue);
			LogPayloadType.Numeric: isDuplicate := (numericValue = lastLogEvent.payload.numericValue);
		END_CASE;
	END_IF;

	IF isDuplicate AND ((now - lastLogEvent.logEventDate) < suppressDuration) THEN
		(* Increment repeat counter instead of storing new entry *)
		logBuffer.cmd := LogCmd.IncrementLast;
	ELSE
		(* Prepare the new log event entry *)
		IF logEventId = '' THEN
			SysTimeRtcHighResGet(pTimestamp := timestamp);
			uuid := CONCAT(loggerName, '-');
			uuid := CONCAT(uuid, ULINT_TO_STRING(timestamp));
			lastLogEvent.logEventId := uuid;
		ELSE
			lastLogEvent.logEventId := logEventId;
		END_IF;
	
		lastLogEvent.loggerName := loggerName;
		lastLogEvent.level := level;
		lastLogEvent.marker := marker;
		lastLogEvent.logEventDate := now;
		lastLogEvent.source := source;
		lastLogEvent.payloadType := payloadType;
		lastLogEvent.repeatCount := 1;
		(* lastLogEvent.contextData := contextData; *)

		CASE payloadType OF
			LogPayloadType.Text : lastLogEvent.payload.message := message;
			LogPayloadType.Enum : lastLogEvent.payload.enumValue := enumValue;
			LogPayloadType.Numeric: lastLogEvent.payload.numericValue := numericValue;
		END_CASE;

		(* Append the new log event *)
		logBuffer.logEntry := lastLogEvent;
		logBuffer.cmd := LogCmd.Push;
	END_IF;

	(* Execute local buffer operation *)
	logBuffer();
	logBuffer.cmd := LogCmd.Idle;

	done := logBuffer.done;
	error := error OR logBuffer.error;
	END_FUNCTION_BLOCK

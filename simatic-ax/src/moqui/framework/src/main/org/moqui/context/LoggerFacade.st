(* 
 * Logger with local circular buffer and duplicate suppression. 
 * Designed for central orchestration by a global LogAppender.
 *)
FUNCTION_BLOCK LoggerFacade
	VAR_EXTERNAL CONSTANT
		defaultLogLevel : LogLevel;
		defaultLogSuppressDuration : TIME;
		defaultLogSuppressDuplicates : BOOL;
		LOG_SOURCE_LIST_MAX_SIZE : UINT;
	END_VAR
	VAR_EXTERNAL
		logSourceList : ARRAY[1..LOG_SOURCE_LIST_MAX_SIZE] OF LogSource;
		logSourceListSize : UINT;
	END_VAR
	(* Log event data *)
	VAR_INPUT
		enable : BOOL;
		logEventId : STRING := '';
		loggerName : STRING;
		level : LogLevel := defaultLogLevel;
		marker : LogMarker := LogMarker#Diagnostics;
		source : STRING;
		payloadType : LogPayloadType := LogPayloadType#Text;
		message : STRING;
		enumValue : UINT;
		numericValue : LREAL;
	END_VAR
	(* Configuration parameters *)
	VAR_INPUT
		suppressDuplicates : BOOL := defaultLogSuppressDuplicates;
		suppressDuration : TIME := defaultLogSuppressDuration;
	END_VAR
	VAR_OUTPUT
		done : BOOL;
		error : BOOL;
	END_VAR
	VAR
		(* Local log ring buffer *)
		logBuffer : LogRingBuffer;
		init : BOOL := FALSE;
		isDuplicate : BOOL;
		now : DATE_AND_TIME;
		lastLogEvent : LogEvent;
		(* Log event ID generator *)
		eventSequence : UDINT := UDINT#0;
	END_VAR

	(* Register once into the log appender source list *)
	IF NOT init THEN
		IF logSourceListSize < LOG_SOURCE_LIST_MAX_SIZE THEN
			logSourceListSize := logSourceListSize + UINT#1;
			logSourceList[logSourceListSize].logRef := REF(logBuffer);
		ELSE
			error := TRUE;
		END_IF;
		init := TRUE;
	END_IF;

	IF NOT enable THEN
		done := FALSE;
		RETURN;
	END_IF;

	now := nowTimestamp();
	isDuplicate := FALSE;

	(* Compression logic (duplicate suppression) *)
	IF suppressDuplicates AND (payloadType = lastLogEvent.payloadType)
			AND (loggerName = lastLogEvent.loggerName)
			AND (source = lastLogEvent.source) THEN
		CASE payloadType OF
			LogPayloadType#Text: isDuplicate := (message = lastLogEvent.payload.message);
			LogPayloadType#Enum: isDuplicate := (enumValue = lastLogEvent.payload.enumValue);
			LogPayloadType#Numeric: isDuplicate := (numericValue = lastLogEvent.payload.numericValue);
		END_CASE;
	END_IF;

	IF isDuplicate AND ((now - lastLogEvent.logEventDate) < suppressDuration) THEN
		(* Increment repeat counter instead of storing new entry *)
		logBuffer.cmd := LogCmd#IncrementLast;
	ELSE
		(* Prepare the new log event entry *)
		IF logEventId = '' THEN
			eventSequence := eventSequence + UDINT#1;
			lastLogEvent.logEventId := loggerName;
		ELSE
			lastLogEvent.logEventId := logEventId;
		END_IF;

		lastLogEvent.loggerName := loggerName;
		lastLogEvent.level := level;
		lastLogEvent.marker := marker;
		lastLogEvent.logEventDate := now;
		lastLogEvent.source := source;
		lastLogEvent.payloadType := payloadType;
		lastLogEvent.repeatCount := UINT#1;

		CASE payloadType OF
			LogPayloadType#Text: lastLogEvent.payload.message := message;
			LogPayloadType#Enum: lastLogEvent.payload.enumValue := enumValue;
			LogPayloadType#Numeric: lastLogEvent.payload.numericValue := numericValue;
		END_CASE;

		(* Append the new log event *)
		logBuffer.logEntry := lastLogEvent;
		logBuffer.cmd := LogCmd#Push;
	END_IF;

	(* Execute local buffer operation *)
	logBuffer();
	logBuffer.cmd := LogCmd#Idle;

	done := logBuffer.done;
	error := error OR logBuffer.error;
END_FUNCTION_BLOCK

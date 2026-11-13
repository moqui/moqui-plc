USING System.Strings;

(*
 * Logger with local circular buffer and duplicate suppression.
 * Designed for central orchestration by a global LogAppender.
 *
 * - Level threshold: events below the global logMinLevel are ignored, as a log4j logger level.
 * - Duplicate suppression: an event equal to the last stored one (same logger, source, level, marker, payload
 *   type and value) within suppressDuration is only counted. The count is written later as one summary record,
 *   a copy of the event with repeatCount = repetitions, when a different event arrives or when the window has
 *   elapsed at any later call ("last message repeated N times"). Stored records are never modified.
 * - The local LogRingBuffer has this block as its only producer: call it from one task only.
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
		logSourceListSize : DINT;
		logMinLevel : LogLevel;
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
		(* The event was stored, or counted as a repetition *)
		done : BOOL;
		(* The block could not register its buffer: LOG_SOURCE_LIST_MAX_SIZE is too small *)
		error : BOOL;
		(* The event, or a pending repetition summary, was refused because the local buffer was full *)
		dropped : BOOL;
	END_VAR
	VAR
		(* Local log ring buffer *)
		logBuffer : LogRingBuffer;
		init : BOOL := FALSE;
		registered : BOOL;
		sourceSlot : DINT;
		isDuplicate : BOOL;
		now : DATE_AND_TIME;
		(* Last stored event, and repetitions of it not yet written *)
		lastLogEvent : LogEvent;
		hasLastLogEvent : BOOL;
		repeatPending : UINT;
		lastRepeatDate : DATE_AND_TIME;
		summary : LogEvent;
		eventRank : INT;
		minRank : INT;
		(* Log event ID generator *)
		eventSequence : UDINT := UDINT#0;
	END_VAR

	done := FALSE;
	error := FALSE;
	dropped := FALSE;

	(* Register once into the log appender source list *)
	IF NOT init THEN
		init := TRUE;
		logSourceListSize := logSourceListSize + DINT#1;
		sourceSlot := logSourceListSize;
		registered := (sourceSlot >= DINT#1) AND (sourceSlot <= TO_DINT(LOG_SOURCE_LIST_MAX_SIZE));
		IF registered THEN
			logSourceList[TO_UINT(sourceSlot)].logRef := REF(logBuffer);
		END_IF;
	END_IF;

	error := NOT registered;
	IF NOT enable OR NOT registered THEN RETURN; END_IF;

	now := nowTimestamp();

	(* Write the pending repetition summary once its window has elapsed *)
	IF (repeatPending > UINT#0) AND ((now - lastLogEvent.logEventDate) >= suppressDuration) THEN
		summary := lastLogEvent;
		summary.logEventId := Concat(lastLogEvent.logEventId, '-repeated');
		summary.logEventDate := lastRepeatDate;
		summary.repeatCount := repeatPending;
		repeatPending := UINT#0;
		logBuffer(cmd := LogCmd#Push, logEntry := summary);
		dropped := logBuffer.dropped;
	END_IF;

	(* Level threshold: All is the lowest threshold, Off disables logging *)
	CASE level OF
		LogLevel#Trace: eventRank := INT#0;
		LogLevel#Debug: eventRank := INT#1;
		LogLevel#Info: eventRank := INT#2;
		LogLevel#Warn: eventRank := INT#3;
		LogLevel#Error: eventRank := INT#4;
		LogLevel#Fatal: eventRank := INT#5;
	ELSE
		eventRank := INT#-1;
	END_CASE;
	CASE logMinLevel OF
		LogLevel#Trace, LogLevel#All: minRank := INT#0;
		LogLevel#Debug: minRank := INT#1;
		LogLevel#Info: minRank := INT#2;
		LogLevel#Warn: minRank := INT#3;
		LogLevel#Error: minRank := INT#4;
		LogLevel#Fatal: minRank := INT#5;
	ELSE
		minRank := INT#6;
	END_CASE;
	IF (eventRank < INT#0) OR (eventRank < minRank) THEN RETURN; END_IF;

	(* Compression logic (duplicate suppression) *)
	isDuplicate := FALSE;
	IF hasLastLogEvent AND suppressDuplicates AND (payloadType = lastLogEvent.payloadType)
			AND (loggerName = lastLogEvent.loggerName)
			AND (source = lastLogEvent.source)
			AND (level = lastLogEvent.level)
			AND (marker = lastLogEvent.marker)
			AND ((now - lastLogEvent.logEventDate) < suppressDuration) THEN
		CASE payloadType OF
			LogPayloadType#Text: isDuplicate := (message = lastLogEvent.payload.message);
			LogPayloadType#Enum: isDuplicate := (enumValue = lastLogEvent.payload.enumValue);
			LogPayloadType#Numeric: isDuplicate := (numericValue = lastLogEvent.payload.numericValue);
		END_CASE;
	END_IF;

	IF isDuplicate THEN
		(* Count the repetition; the summary record is written later *)
		IF repeatPending < UINT#65535 THEN repeatPending := repeatPending + UINT#1; END_IF;
		lastRepeatDate := now;
		done := TRUE;
		RETURN;
	END_IF;

	(* A different event: first write the repetitions of the previous one *)
	IF repeatPending > UINT#0 THEN
		summary := lastLogEvent;
		summary.logEventId := Concat(lastLogEvent.logEventId, '-repeated');
		summary.logEventDate := lastRepeatDate;
		summary.repeatCount := repeatPending;
		repeatPending := UINT#0;
		logBuffer(cmd := LogCmd#Push, logEntry := summary);
		dropped := dropped OR logBuffer.dropped;
	END_IF;

	(* Prepare the new log event entry *)
	IF logEventId = '' THEN
		eventSequence := eventSequence + UDINT#1;
		lastLogEvent.logEventId := Concat(Concat(loggerName, '-'), ToString(eventSequence));
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
	logBuffer(cmd := LogCmd#Push, logEntry := lastLogEvent);
	logBuffer.cmd := LogCmd#Idle;

	done := logBuffer.done;
	dropped := dropped OR logBuffer.dropped;
	(* A refused event must not be followed by repetitions of it: the next equal event is stored as new *)
	hasLastLogEvent := logBuffer.done;
END_FUNCTION_BLOCK

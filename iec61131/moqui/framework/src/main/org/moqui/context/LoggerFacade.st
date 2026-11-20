(*
 * Logger with local circular buffer and duplicate suppression.
 * Designed for central orchestration by a global LogAppender.
 *
 * - Level threshold: events below the global logMinLevel are ignored, as a log4j logger level.
 * - Duplicate suppression: an event equal to the last stored one (same logger, source, level, marker, payload
 *   type and value) within suppressDuration is only counted. The count is written later as one summary record,
 *   a copy of the event with repeatCount = repetitions, when a different event arrives or when the window has
 *   elapsed at any later call ("last message repeated N times"). Stored records are never modified.
 * - Rate limit: at most maxEventsPerWindow new events are stored in one suppressDuration window. Further
 *   events are only counted; at the first call after the window one Warn event reports how many were suppressed.
 *   Repetitions counted by duplicate suppression do not count against the limit.
 * - The local LogRingBuffer has this block as its only producer: call it from one task only.
 * - Inputs are retained between calls, as for every function block: pass level at every call,
 *   otherwise the event gets the level of the previous call.
 * - Generated logEventId: loggerName-<ms timestamp>-<source slot>-<event count>. The slot is unique per facade,
 *   the count per event of the facade, and the timestamp separates restarts of the application.
 *)
FUNCTION_BLOCK LoggerFacade
	VAR_EXTERNAL CONSTANT
		defaultLogLevel : LogLevel;
		defaultLogSuppressDuration : TIME;
		defaultLogSuppressDuplicates : BOOL;
		defaultLogMaxEventsPerWindow : UINT;
		LOG_SOURCE_LIST_MAX_SIZE : UINT;
	END_VAR
	VAR_EXTERNAL
		logSourceList : ARRAY[1..LOG_SOURCE_LIST_MAX_SIZE] OF LogSource;
	    logSourceListSize : DINT;
		logMinLevel : LogLevel;
	END_VAR
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
	    level : LogLevel := defaultLogLevel;
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
		suppressDuplicates : BOOL := defaultLogSuppressDuplicates;
	    (* Duplicate suppression window *)
	    suppressDuration : TIME := defaultLogSuppressDuration;
	    (* Rate limit: new events stored per suppressDuration window (0 disables) *)
	    maxEventsPerWindow : UINT := defaultLogMaxEventsPerWindow;
	END_VAR
	VAR_OUTPUT
		(* The event was stored, or counted as a repetition *)
		done : BOOL;
		(* The block could not register its buffer: LOG_SOURCE_LIST_MAX_SIZE is too small *)
		error : BOOL;
		(* The event, or a pending repetition summary, was refused because the local buffer was full *)
		dropped : BOOL;
		(* The event was not stored: the rate limit of the window was reached *)
		rateLimited : BOOL;
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
	    minLevel : INT;
		(* Log event ID generator *)
	    uuid : STRING;
	    eventCount : UDINT;
	    (* Rate limit window *)
	    windowOpen : BOOL;
	    windowStart : DATE_AND_TIME;
	    windowEventCount : UINT;
	    windowSuppressed : UDINT;
	    rateNotice : LogEvent;
	END_VAR

	done := FALSE;
	error := FALSE;
	dropped := FALSE;
	rateLimited := FALSE;

	(* Register once into the log appender source list; the atomic increment gives each facade its own slot *)
	IF NOT init THEN
		init := TRUE;
		sourceSlot := __XADD(ADR(logSourceListSize), 1) + 1;
		registered := (sourceSlot >= 1) AND (sourceSlot <= UINT_TO_DINT(LOG_SOURCE_LIST_MAX_SIZE));
		IF registered THEN
			logSourceList[DINT_TO_UINT(sourceSlot)].logRef REF= logBuffer;
		END_IF;
	END_IF;

	error := NOT registered;
	IF NOT enable OR NOT registered THEN RETURN; END_IF;

	now := nowTimestamp();

	(* Rate limit: at the end of the window report the suppressed events, then open a new window *)
	IF NOT windowOpen OR ((now - windowStart) >= suppressDuration) THEN
		IF (windowSuppressed > 0) AND (logMinLevel <> LogLevel.Off) THEN
			eventCount := eventCount + 1;
			rateNotice.logEventId := CONCAT(loggerName, '-suppressed-');
			rateNotice.logEventId := CONCAT(rateNotice.logEventId, ULINT_TO_STRING(nowMillis()));
			rateNotice.logEventId := CONCAT(rateNotice.logEventId, '-');
			rateNotice.logEventId := CONCAT(rateNotice.logEventId, DINT_TO_STRING(sourceSlot));
			rateNotice.logEventId := CONCAT(rateNotice.logEventId, '-');
			rateNotice.logEventId := CONCAT(rateNotice.logEventId, UDINT_TO_STRING(eventCount));
			rateNotice.loggerName := loggerName;
			rateNotice.level := LogLevel.Warn;
			rateNotice.marker := LogMarker.Health;
			rateNotice.logEventDate := now;
			(* A device event, not a parameter value: empty source (DeviceLog of loggerName) *)
			rateNotice.source := '';
			rateNotice.payloadType := LogPayloadType.Text;
			rateNotice.payload.message := CONCAT(UDINT_TO_STRING(windowSuppressed),
				' log events suppressed: logger too verbose');
			rateNotice.repeatCount := 1;
			logBuffer(cmd := LogCmd.Push, logEntry := rateNotice);
			logBuffer.cmd := LogCmd.Idle;
			dropped := logBuffer.dropped;
		END_IF;
		windowOpen := TRUE;
		windowStart := now;
		windowEventCount := 0;
		windowSuppressed := 0;
	END_IF;

	(* Write the pending repetition summary once its window has elapsed *)
	IF (repeatPending > 0) AND ((now - lastLogEvent.logEventDate) >= suppressDuration) THEN
		summary := lastLogEvent;
		summary.logEventId := CONCAT(lastLogEvent.logEventId, '-repeated');
		summary.logEventDate := lastRepeatDate;
		summary.repeatCount := repeatPending;
		repeatPending := 0;
		logBuffer(cmd := LogCmd.Push, logEntry := summary);
		dropped := dropped OR logBuffer.dropped;
	END_IF;

	(* Level threshold: All is the lowest threshold, Off disables logging *)
	minLevel := TO_INT(logMinLevel);
	IF logMinLevel = LogLevel.All THEN minLevel := TO_INT(LogLevel.Trace); END_IF;
	IF (logMinLevel = LogLevel.Off) OR (TO_INT(level) < minLevel) OR (TO_INT(level) > TO_INT(LogLevel.Fatal)) THEN
		RETURN;
	END_IF;

	(* Compression logic (duplicate suppression) *)
	isDuplicate := FALSE;
	IF hasLastLogEvent AND suppressDuplicates AND (payloadType = lastLogEvent.payloadType)
	        AND (loggerName = lastLogEvent.loggerName)
			AND (source = lastLogEvent.source)
			AND (level = lastLogEvent.level)
			AND (marker = lastLogEvent.marker)
			AND ((now - lastLogEvent.logEventDate) < suppressDuration) THEN
		CASE payloadType OF
			LogPayloadType.Text: isDuplicate := (message = lastLogEvent.payload.message);
			LogPayloadType.Enum: isDuplicate := (enumValue = lastLogEvent.payload.enumValue);
			LogPayloadType.Numeric: isDuplicate := (numericValue = lastLogEvent.payload.numericValue);
		END_CASE;
	END_IF;

	IF isDuplicate THEN
		(* Count the repetition; the summary record is written later *)
		IF repeatPending < 65535 THEN repeatPending := repeatPending + 1; END_IF;
		lastRepeatDate := now;
		done := TRUE;
		RETURN;
	END_IF;

	(*
	 * Rate limit: over the limit the new event is only counted. Checked before the repetition summary,
	 * so alternating events cannot write one summary per call; the summary is written when the window elapses.
	 *)
	IF (maxEventsPerWindow > 0) AND (windowEventCount >= maxEventsPerWindow) THEN
		IF windowSuppressed < 16#FFFFFFFF THEN windowSuppressed := windowSuppressed + 1; END_IF;
		rateLimited := TRUE;
		RETURN;
	END_IF;
	windowEventCount := windowEventCount + 1;

	(* A different event: first write the repetitions of the previous one *)
	IF repeatPending > 0 THEN
		summary := lastLogEvent;
		summary.logEventId := CONCAT(lastLogEvent.logEventId, '-repeated');
		summary.logEventDate := lastRepeatDate;
		summary.repeatCount := repeatPending;
		repeatPending := 0;
		logBuffer(cmd := LogCmd.Push, logEntry := summary);
		dropped := dropped OR logBuffer.dropped;
	END_IF;

	(* Prepare the new log event entry *)
	IF logEventId = '' THEN
		(* Two events of one cycle share the ms timestamp, and facades can share loggerName: slot and count keep the ID unique *)
		eventCount := eventCount + 1;
		uuid := CONCAT(loggerName, '-');
		uuid := CONCAT(uuid, ULINT_TO_STRING(nowMillis()));
		uuid := CONCAT(uuid, '-');
		uuid := CONCAT(uuid, DINT_TO_STRING(sourceSlot));
		uuid := CONCAT(uuid, '-');
		uuid := CONCAT(uuid, UDINT_TO_STRING(eventCount));
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
	logBuffer(cmd := LogCmd.Push, logEntry := lastLogEvent);
	logBuffer.cmd := LogCmd.Idle;

	done := logBuffer.done;
	dropped := dropped OR logBuffer.dropped;
	(* A refused event must not be followed by repetitions of it: the next equal event is stored as new *)
	hasLastLogEvent := logBuffer.done;
	END_FUNCTION_BLOCK

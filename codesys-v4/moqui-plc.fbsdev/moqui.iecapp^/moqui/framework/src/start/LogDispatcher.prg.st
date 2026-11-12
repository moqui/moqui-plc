PROGRAM LogDispatcher
	
	VAR
	    done, busy, error : BOOL;
	    errorId : INT; (* 120 : LogSourceErr *)
	    (* MQTT log appender *)
	    logAppender : MqttLogAppender;
	    currentSource : REFERENCE TO LogSource;
		currentLogBuffer : ARRAY[1..MoquiConf.LOG_MAX_SIZE] OF LogEvent;
	 	currentHead : UINT;
	    currentTail : UINT;
	    currentOverflowCount : UDINT;
	    currentLogSize : UINT;
	    sourceIndex : UINT := 1;
	END_VAR

	IF NOT ec.logAppenderEnable OR (ec.logSourceListSize = 0) THEN 
	    done := FALSE; busy := FALSE; error := FALSE; errorId := 0;
	    RETURN;
	END_IF;

	IF NOT logAppender.busy THEN
	    IF sourceIndex < 1 OR sourceIndex > ec.logSourceListSize THEN sourceIndex := 1; END_IF;

	    currentSource REF= ec.logSourceList[sourceIndex];
		(* Snapshot of the current metadata *)
		currentLogBuffer := currentSource.logRef.logBuffer;
	    currentHead := currentSource.logRef.head;
	    currentTail := currentSource.logRef.tail;
	    currentOverflowCount := currentSource.logRef.overflowCount;
	    currentLogSize := currentSource.logRef.logSize;

	    (*
	     * Skip this source if:
	     *   - the buffer is empty, OR
	     *   - fewer than LOG_APPENDER_BATCH_SIZE entries accumulated AND no overflow (no urgency).
	     * Overflow bypasses the batch threshold to avoid losing entries.
	     *)
	    IF currentSource.logRef.isEmpty OR
	            ((currentLogSize - currentSource.lastLogSize) < MoquiConf.LOG_APPENDER_BATCH_SIZE) AND
	             (currentOverflowCount <= currentSource.lastOverflowCount) THEN
	        sourceIndex := (sourceIndex MOD ec.logSourceListSize) + 1;
	        RETURN;
	    END_IF;

	    (* Source ready: Commit snapshot metadata to LogSource *)
	    currentSource.lastHead := currentHead;
	    currentSource.lastTail := currentTail;
	    currentSource.lastOverflowCount := currentOverflowCount;
	    currentSource.lastLogSize := currentLogSize;
	END_IF;

	logAppender(execute := TRUE, logBuffer := currentLogBuffer, logBufferSize := currentLogSize,
		done => done, busy => busy, error => error, errorId => errorId);

	IF logAppender.done OR logAppender.error THEN
	    logAppender(execute := FALSE, done => done, busy => busy,
	        error => error, errorId => errorId);    
	    (* Go to next log source *)
	    sourceIndex := (sourceIndex MOD ec.logSourceListSize) + 1;
	END_IF;
	END_PROGRAM

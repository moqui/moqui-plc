(*
 * Bounded log queue between one producer and one consumer, without locks and without waits.
 *
 * - Producer: the LoggerFacade that owns this instance, in its own task. It calls the block with cmd := LogCmd#Push,
 *   writes logBuffer[writeSlot] and only then publishes the record by incrementing writeCount.
 * - Consumer: reads the records between readCount and writeCount, starting from its LogSource.readSlot, and
 *   releases them by incrementing readCount. The AX port has no consumer yet: the queue fills and then refuses.
 *
 * Each counter has a single writer. The S7-1500 runs the user program on one core and a 32-bit aligned write is
 * atomic, so a task that preempts another sees the counters in program order; the canonical CODESYS source uses
 * __XADD for multicore targets. When the queue is full the new record is refused and counted in droppedCount.
 *)
FUNCTION_BLOCK LogRingBuffer
	VAR_EXTERNAL CONSTANT
	    LOG_MAX_SIZE : UINT;
	END_VAR
	VAR_INPUT
	    cmd : LogCmd := LogCmd#Idle;
	    logEntry : LogEvent;
	END_VAR
	VAR_OUTPUT
	    done : BOOL;
	    error : BOOL;
	    (* The record was refused because the queue was full *)
	    dropped : BOOL;
	    logBuffer : ARRAY[1..LOG_MAX_SIZE] OF LogEvent;
	    (* Records ever written (producer-owned); wraps around, only differences are meaningful *)
	    writeCount : DINT;
	    (* Records ever released (consumer-owned) *)
	    readCount : DINT;
	    (* Records refused because the queue was full (producer-owned) *)
	    droppedCount : UDINT;
	    isFull : BOOL;
	    isEmpty : BOOL;
	END_VAR
	VAR
	    writeSlot : UINT := UINT#1;
	    pending : DINT;
	END_VAR

	done := FALSE;
	error := FALSE;
	dropped := FALSE;

	IF cmd = LogCmd#Idle THEN RETURN; END_IF;
	IF (cmd <> LogCmd#Push) OR (writeSlot < UINT#1) OR (writeSlot > LOG_MAX_SIZE) THEN
	    error := TRUE;
	    RETURN;
	END_IF;

	pending := writeCount - readCount;
	IF (pending < DINT#0) OR (pending >= TO_DINT(LOG_MAX_SIZE)) THEN
	    (* Full, or counters out of range: refuse the record, never overwrite unreleased records *)
	    IF droppedCount < UDINT#16#FFFFFFFF THEN droppedCount := droppedCount + UDINT#1; END_IF;
	    dropped := TRUE;
	    isFull := TRUE;
	    isEmpty := FALSE;
	    RETURN;
	END_IF;

	logBuffer[writeSlot] := logEntry;
	logBuffer[writeSlot].sequence := TO_UDINT(writeCount) + UDINT#1;
	writeSlot := (writeSlot MOD LOG_MAX_SIZE) + UINT#1;
	(* Publish the record after it is complete *)
	writeCount := writeCount + DINT#1;
	done := TRUE;

	isFull := (pending + DINT#1) >= TO_DINT(LOG_MAX_SIZE);
	isEmpty := FALSE;
END_FUNCTION_BLOCK

(*
 * Bounded log queue between one producer and one consumer, without locks and without waits.
 *
 * - Producer: the LoggerFacade that owns this instance, in its own task. It calls the block with cmd := LogCmd.Push,
 *   writes logBuffer[writeSlot] and only then publishes the record by incrementing writeCount.
 * - Consumer: LogDispatcher. It reads the records between readCount and writeCount, starting from its
 *   LogSource.readSlot, and releases them by incrementing readCount once they are published or discarded.
 *
 * Each counter has a single writer, and both are read and incremented only with __XADD, an atomic operation that is
 * also a memory barrier: a published record is complete before the consumer sees it, and a released slot is no longer
 * read when the producer reuses it. When the queue is full the new record is refused and counted in droppedCount: the
 * producer never moves the consumer's position, so the two tasks never write the same variable.
 *)
FUNCTION_BLOCK LogRingBuffer
	
	VAR_INPUT
	    cmd : LogCmd := LogCmd.Idle;
	    logEntry : LogEvent;
	END_VAR
	VAR_OUTPUT
	    done, error : BOOL;
	    (* The record was refused because the queue was full *)
	    dropped : BOOL;
	    logBuffer : ARRAY[1..MoquiConf.LOG_MAX_SIZE] OF LogEvent;
	    (* Records ever written (producer-owned); wraps around, only differences are meaningful *)
	    writeCount : DINT;
	    (* Records ever released (consumer-owned, incremented by LogDispatcher with __XADD) *)
	    readCount : DINT;
	    (* Records refused because the queue was full (producer-owned) *)
	    droppedCount : UDINT;
	    isFull, isEmpty : BOOL;
	END_VAR
	VAR
	    writeSlot : UINT := 1;
	    released : DINT;
	    pending : DINT;
	    previous : DINT;
	END_VAR

	done := FALSE;
	error := FALSE;
	dropped := FALSE;

	IF cmd = LogCmd.Idle THEN RETURN; END_IF;
	IF (cmd <> LogCmd.Push) OR (writeSlot < 1) OR (writeSlot > MoquiConf.LOG_MAX_SIZE) THEN
	    error := TRUE;
	    RETURN;
	END_IF;

	(* Atomic read of the consumer's count: adding 0 changes nothing *)
	released := __XADD(ADR(readCount), 0);
	pending := writeCount - released;
	IF (pending < 0) OR (pending >= UINT_TO_DINT(MoquiConf.LOG_MAX_SIZE)) THEN
	    (* Full, or counters out of range: refuse the record, never overwrite unreleased records *)
	    IF droppedCount < 16#FFFFFFFF THEN droppedCount := droppedCount + 1; END_IF;
	    dropped := TRUE;
	    isFull := TRUE;
	    isEmpty := FALSE;
	    RETURN;
	END_IF;

	logBuffer[writeSlot] := logEntry;
	logBuffer[writeSlot].sequence := DINT_TO_UDINT(writeCount) + 1;
	writeSlot := (writeSlot MOD MoquiConf.LOG_MAX_SIZE) + 1;
	(* Publish the record: the consumer reads writeCount with __XADD too *)
	previous := __XADD(ADR(writeCount), 1);
	done := TRUE;

	isFull := (pending + 1) >= UINT_TO_DINT(MoquiConf.LOG_MAX_SIZE);
	isEmpty := FALSE;
	END_FUNCTION_BLOCK

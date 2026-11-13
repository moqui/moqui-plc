(*
 * Log pipeline test suite: LogRingBuffer, LoggerFacade registration, level threshold and duplicate summaries.
 * It runs once; passed is TRUE when every check holds, otherwise failedCheck is the number of the first failed check.
 *
 * Run it in its own test task with MqttCommunication not running: the suite reads the registered buffer itself,
 * and LogDispatcher would otherwise publish and release the test records.
 *)
PROGRAM LogTestSuite
	VAR_EXTERNAL CONSTANT
		LOG_MAX_SIZE : UINT;
		LOG_SOURCE_LIST_MAX_SIZE : UINT;
	END_VAR
	VAR_EXTERNAL
		logSourceList : ARRAY[1..LOG_SOURCE_LIST_MAX_SIZE] OF LogSource;
		logSourceListSize : DINT;
		logMinLevel : LogLevel;
	END_VAR
	VAR
		finished : BOOL;
		passed : BOOL;
		checks : UINT;
		failedCheck : UINT;
		ring : LogRingBuffer;
		facade : LoggerFacade;
		event : LogEvent;
		source : REFERENCE TO LogSource;
		savedMinLevel : LogLevel;
		writtenBefore : DINT;
		i : UINT;
		previous : DINT;
		ok : BOOL;
	END_VAR

	IF finished THEN RETURN; END_IF;
	finished := TRUE;
	passed := TRUE;

	(* ========== LogRingBuffer: fills, refuses without overwriting, accepts again once released ========== *)
	event.loggerName := 'LOG_TEST';
	event.payloadType := LogPayloadType.Text;
	event.payload.message := 'ring';
	ok := TRUE;
	FOR i := 1 TO LOG_MAX_SIZE DO
		ring(cmd := LogCmd.Push, logEntry := event);
		ok := ok AND ring.done AND NOT ring.dropped;
	END_FOR;
	checks := checks + 1; IF NOT ok AND (failedCheck = 0) THEN failedCheck := checks; END_IF;
	checks := checks + 1; IF NOT ring.isFull AND (failedCheck = 0) THEN failedCheck := checks; END_IF;

	ring(cmd := LogCmd.Push, logEntry := event);
	checks := checks + 1; IF NOT (ring.dropped AND (ring.droppedCount = 1) AND NOT ring.done) AND (failedCheck = 0) THEN failedCheck := checks; END_IF;
	checks := checks + 1; IF NOT ((ring.logBuffer[1].sequence = 1) AND (ring.logBuffer[LOG_MAX_SIZE].sequence = LOG_MAX_SIZE))
			AND (failedCheck = 0) THEN failedCheck := checks; END_IF;

	(* The consumer releases one record: its slot is reused by the next record *)
	previous := __XADD(ADR(ring.readCount), 1);
	ring(cmd := LogCmd.Push, logEntry := event);
	checks := checks + 1; IF NOT (ring.done AND (ring.logBuffer[1].sequence = UINT_TO_UDINT(LOG_MAX_SIZE) + 1))
			AND (failedCheck = 0) THEN failedCheck := checks; END_IF;
	checks := checks + 1; IF NOT ((ring.writeCount - ring.readCount) = UINT_TO_DINT(LOG_MAX_SIZE)) AND (failedCheck = 0) THEN failedCheck := checks; END_IF;

	(* ========== LoggerFacade: registration, level threshold, duplicate summary ========== *)
	savedMinLevel := logMinLevel;
	logMinLevel := LogLevel.Info;

	facade.enable := TRUE;
	facade.loggerName := 'LOG_TEST';
	facade.level := LogLevel.Info;
	facade.suppressDuplicates := TRUE;
	facade.suppressDuration := T#1H;

	facade(message := 'first');
	checks := checks + 1; IF NOT (facade.done AND NOT facade.error) AND (failedCheck = 0) THEN failedCheck := checks; END_IF;
	checks := checks + 1; IF NOT ((logSourceListSize >= 1) AND (logSourceListSize <= UINT_TO_DINT(LOG_SOURCE_LIST_MAX_SIZE)))
			AND (failedCheck = 0) THEN failedCheck := checks; END_IF;

	IF failedCheck = 0 THEN
		source REF= logSourceList[DINT_TO_UINT(logSourceListSize)];
		writtenBefore := source.logRef.writeCount;

		(* Two repetitions are only counted *)
		facade(message := 'first');
		facade(message := 'first');
		checks := checks + 1; IF NOT (facade.done AND (source.logRef.writeCount = writtenBefore)) AND (failedCheck = 0) THEN failedCheck := checks; END_IF;

		(* A Debug event is below the threshold *)
		facade(message := 'debug', level := LogLevel.Debug);
		checks := checks + 1; IF NOT (NOT facade.done AND (source.logRef.writeCount = writtenBefore)) AND (failedCheck = 0) THEN failedCheck := checks; END_IF;

		(* A different event writes the summary of the repetitions, then itself *)
		facade(message := 'second', level := LogLevel.Info);
		checks := checks + 1; IF NOT (source.logRef.writeCount = writtenBefore + 2) AND (failedCheck = 0) THEN failedCheck := checks; END_IF;
		checks := checks + 1; IF NOT ((source.logRef.logBuffer[2].repeatCount = 2) AND (source.logRef.logBuffer[2].payload.message = 'first')
				AND (source.logRef.logBuffer[3].repeatCount = 1) AND (source.logRef.logBuffer[3].payload.message = 'second'))
				AND (failedCheck = 0) THEN failedCheck := checks; END_IF;
		checks := checks + 1; IF NOT ((source.logRef.logBuffer[1].sequence = 1) AND (source.logRef.logBuffer[3].sequence = 3))
				AND (failedCheck = 0) THEN failedCheck := checks; END_IF;
	END_IF;

	logMinLevel := savedMinLevel;
	passed := failedCheck = 0;
	END_PROGRAM

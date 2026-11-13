(*
 * Log dispatcher: the only consumer of the LoggerFacade buffers registered in logSourceList.
 * MqttCommunication calls it after the broker connection has been serviced, in the same task.
 *
 * - The sources are visited in turn; one batch of at most LOG_APPENDER_BATCH_SIZE records of one source is copied
 *   and published as one MQTT message (MqttLogAppender).
 * - The records are released from their buffer only when the batch has been published (QoS 1: acknowledged).
 *   A failed batch is built again and resent with the DUP flag, up to logPublishMaxAttempts times; then it is
 *   released and counted in LogSource.discardedCount. While the broker is not connected nothing is taken, and the
 *   buffers keep their records until they are full.
 * - Records refused by a full buffer are reported in the next batch of that source by one record
 *   "N log events dropped" (Warn, Health, device-scoped on applicationDeviceId).
 * - When a batch does not fit the JSON capacity, batchLimit is halved and the batch built again.
 *
 * errorId: 121 inconsistent buffer counters, 122 batch not finished within SEND_TIMEOUT; otherwise the
 * MqttLogAppender error of the last failed attempt.
 *)
PROGRAM LogDispatcher
	
	VAR CONSTANT
	    STATE_SELECT : USINT := 0;
	    STATE_BUILD : USINT := 1;
	    STATE_SEND : USINT := 2;
	    STATE_RELEASE : USINT := 3;
	    (* Safety net above the publish timeout: a batch still running after this is a failed attempt *)
	    SEND_TIMEOUT : TIME := T#30S;
	END_VAR
	VAR
	    done, busy, error : BOOL;
	    errorId : INT;
	    (* MQTT log appender *)
	    logAppender : MqttLogAppender;
	    state : USINT := STATE_SELECT;
	    (* After the reset of the appender: build the same batch again *)
	    retryPending : BOOL;
	    sendTimer : TON;
	    (* The batch: an optional drop report, then entryCount records of the active source *)
	    batch : ARRAY[1..MoquiConf.LOG_APPENDER_BATCH_SIZE] OF LogEvent;
	    batchSize : UINT;
	    entryCount : UINT;
	    nextSlot : UINT;
	    batchDropCount : UDINT;
	    batchLimit : UINT := MoquiConf.LOG_APPENDER_BATCH_SIZE;
	    attempts : UINT;
	    activeSource : UINT;
	    sourceIndex : UINT := 1;
	    sourceCount, scan, index, i, slot : UINT;
	    available : DINT;
	    previous : DINT;
	    sourceRef : REFERENCE TO LogSource;
	    dropReport : LogEvent;
	END_VAR

	done := FALSE;

	IF ec.logSourceListSize <= 0 THEN
	    sourceCount := 0;
	ELSIF ec.logSourceListSize >= UINT_TO_DINT(MoquiConf.LOG_SOURCE_LIST_MAX_SIZE) THEN
	    sourceCount := MoquiConf.LOG_SOURCE_LIST_MAX_SIZE;
	ELSE
	    sourceCount := DINT_TO_UINT(ec.logSourceListSize);
	END_IF;

	(* Wait until the appender no longer uses the batch, then select or build again *)
	IF state = STATE_RELEASE THEN
	    logAppender(execute := FALSE);
	    busy := logAppender.busy;
	    IF logAppender.busy THEN RETURN; END_IF;
	    IF retryPending THEN
	        retryPending := FALSE;
	        state := STATE_BUILD;
	    ELSE
	        state := STATE_SELECT;
	    END_IF;
	END_IF;

	IF state = STATE_SELECT THEN
	    busy := FALSE;
	    IF NOT ec.logAppenderEnable OR NOT ec.connectionFactory.connected OR (sourceCount = 0) THEN RETURN; END_IF;
	    IF (sourceIndex < 1) OR (sourceIndex > sourceCount) THEN sourceIndex := 1; END_IF;
	    FOR scan := 1 TO sourceCount DO
	        index := ((sourceIndex + scan - 2) MOD sourceCount) + 1;
	        IF __ISVALIDREF(ec.logSourceList[index].logRef) THEN
	            sourceRef REF= ec.logSourceList[index];
	            available := __XADD(ADR(sourceRef.logRef.writeCount), 0) - sourceRef.logRef.readCount;
	            IF (available <> 0) OR (sourceRef.logRef.droppedCount <> sourceRef.reportedDropCount) THEN
	                activeSource := index;
	                attempts := 0;
	                state := STATE_BUILD;
	                EXIT;
	            END_IF;
	        END_IF;
	    END_FOR;
	    IF state <> STATE_BUILD THEN RETURN; END_IF;
	END_IF;

	IF state = STATE_BUILD THEN
	    sourceRef REF= ec.logSourceList[activeSource];
	    sourceIndex := (activeSource MOD sourceCount) + 1;
	    IF (batchLimit < 1) OR (batchLimit > MoquiConf.LOG_APPENDER_BATCH_SIZE) THEN batchLimit := MoquiConf.LOG_APPENDER_BATCH_SIZE; END_IF;
	    available := __XADD(ADR(sourceRef.logRef.writeCount), 0) - sourceRef.logRef.readCount;
	    IF (available < 0) OR (available > UINT_TO_DINT(MoquiConf.LOG_MAX_SIZE))
	            OR (sourceRef.readSlot < 1) OR (sourceRef.readSlot > MoquiConf.LOG_MAX_SIZE) THEN
	        error := TRUE; errorId := 121;
	        state := STATE_SELECT;
	        RETURN;
	    END_IF;

	    batchSize := 0;
	    batchDropCount := sourceRef.logRef.droppedCount;
	    IF batchDropCount <> sourceRef.reportedDropCount THEN
	        dropReport.logEventId := CONCAT(MoquiConf.applicationDeviceId, '-dropped-');
	        dropReport.logEventId := CONCAT(dropReport.logEventId, UDINT_TO_STRING(batchDropCount));
	        dropReport.loggerName := MoquiConf.applicationDeviceId;
	        dropReport.source := '';
	        dropReport.level := LogLevel.Warn;
	        dropReport.marker := LogMarker.Health;
	        dropReport.logEventDate := nowTimestamp();
	        dropReport.payloadType := LogPayloadType.Text;
	        dropReport.payload.message := CONCAT(UDINT_TO_STRING(batchDropCount - sourceRef.reportedDropCount),
	            ' log events dropped: log buffer full');
	        dropReport.repeatCount := 1;
	        dropReport.sequence := 0;
	        batchSize := 1;
	        batch[1] := dropReport;
	    END_IF;

	    entryCount := batchLimit - batchSize;
	    IF UINT_TO_DINT(entryCount) > available THEN entryCount := DINT_TO_UINT(available); END_IF;
	    slot := sourceRef.readSlot;
	    FOR i := 1 TO entryCount DO
	        batch[batchSize + i] := sourceRef.logRef.logBuffer[slot];
	        slot := (slot MOD MoquiConf.LOG_MAX_SIZE) + 1;
	    END_FOR;
	    batchSize := batchSize + entryCount;
	    nextSlot := slot;

	    IF batchSize = 0 THEN
	        state := STATE_SELECT;
	        RETURN;
	    END_IF;
	    state := STATE_SEND;
	END_IF;

	IF state = STATE_SEND THEN
	    busy := TRUE;
	    sendTimer(IN := TRUE, PT := SEND_TIMEOUT);
	    logAppender(execute := TRUE, logBuffer := batch, logBufferSize := batchSize, redelivery := attempts > 0);

	    IF logAppender.done THEN
	        (* Published: release the records and the reported drops *)
	        sourceRef REF= ec.logSourceList[activeSource];
	        sourceRef.readSlot := nextSlot;
	        previous := __XADD(ADR(sourceRef.logRef.readCount), UINT_TO_DINT(entryCount));
	        sourceRef.reportedDropCount := batchDropCount;
	        IF sourceRef.publishedCount < 16#FFFFFFFF - batchSize THEN
	            sourceRef.publishedCount := sourceRef.publishedCount + batchSize;
	        END_IF;
	        done := TRUE; error := FALSE; errorId := 0;
	        sendTimer(IN := FALSE);
	        state := STATE_RELEASE;
	    ELSIF logAppender.error OR sendTimer.Q THEN
	        error := TRUE;
	        IF sendTimer.Q THEN errorId := 122; ELSE errorId := logAppender.errorId; END_IF;
	        sendTimer(IN := FALSE);
	        IF logAppender.serializeError AND (batchSize > 1) THEN
	            (* The JSON does not fit: try again with half the records *)
	            batchLimit := batchSize / 2;
	            retryPending := TRUE;
	        ELSIF logAppender.error AND (logAppender.errorId = 200) THEN
	            (* Not connected: nothing was sent; the records wait in their buffer *)
	            retryPending := FALSE;
	        ELSE
	            attempts := attempts + 1;
	            IF attempts < MoquiConf.logPublishMaxAttempts THEN
	                retryPending := TRUE;
	            ELSE
	                (* Give up this batch: release it and count it as discarded *)
	                sourceRef REF= ec.logSourceList[activeSource];
	                sourceRef.readSlot := nextSlot;
	                previous := __XADD(ADR(sourceRef.logRef.readCount), UINT_TO_DINT(entryCount));
	                sourceRef.reportedDropCount := batchDropCount;
	                IF sourceRef.discardedCount < 16#FFFFFFFF - batchSize THEN
	                    sourceRef.discardedCount := sourceRef.discardedCount + batchSize;
	                END_IF;
	                retryPending := FALSE;
	            END_IF;
	        END_IF;
	        state := STATE_RELEASE;
	    END_IF;
	END_IF;
	END_PROGRAM

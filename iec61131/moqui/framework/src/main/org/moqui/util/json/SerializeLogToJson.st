(*
 * JSON log generator: one MQTT payload with logBufferSize records, as the map of events the device gateway reads,
 *   {"001":{...},"002":{...}}
 * The keys are the record positions with a fixed width, so a reader that sorts keys keeps the record order.
 * Each record has logEventId, logEventDate, loggerName, source, level, marker, type, repeatCount, sequence and
 * the value of its type (message, enumValue or numericValue).
 *
 * The JSON writer produces UTF-16 (WORD) text; it is encoded once into UTF-8 bytes in jsonPayload. Every builder,
 * writer and capacity error stops the serialization with error = TRUE:
 *   100 JSON data allocation, 110 arguments, 111 JSON element capacity, 112 UTF-8 payload capacity,
 *   113 writer output without terminator; otherwise the JSON writer's error code.
 * Keep execute TRUE until done or error, then set it FALSE (and call once) before the next payload.
 *)
FUNCTION_BLOCK SerializeLogToJson
	VAR_EXTERNAL CONSTANT
	    LOG_APPENDER_BATCH_SIZE : UINT;
	    LOG_JSON_PAYLOAD_MAX_SIZE : UINT;
	    JSON_LINE_BREAK : WSTRING(2);
	END_VAR
	VAR_INPUT
	    execute : BOOL;
	    (* Source: the records to publish, in order *)
	    logBuffer : REFERENCE TO ARRAY[1..LOG_APPENDER_BATCH_SIZE] OF LogEvent;
	    logBufferSize : UINT; (* Number of valid entries in logBuffer, 1..LOG_APPENDER_BATCH_SIZE *)
	    asyncMode : BOOL := TRUE; (* Asynchronous serialization of the writer *)
	    lineBreak : WSTRING(2) := JSON_LINE_BREAK;
	END_VAR
	VAR_OUTPUT
	    done : BOOL; (* JSON successfully generated *)
	    busy : BOOL; (* Serialization in progress *)
	    error : BOOL;
	    errorId : INT;
	    jsonPayload : ARRAY[0..LOG_JSON_PAYLOAD_MAX_SIZE] OF BYTE;
	    payloadSize : UDINT; (* Bytes written, excluding the null terminator; valid when done = TRUE *)
	END_VAR
	VAR
	    (*
		 * JSON helpers.
		 * JSONBuilder constructs a JSON structure in memory, inside a JSONData object.
	     * JSONByteArrayWriter serializes that JSONData structure into a WORD (UTF-16) buffer.
	     *)
	    jsonFactory : JSON.JSONDataFactory;
	    jsonData : POINTER TO JSON.JSONData;
	    jsonBuilder : JSON.JSONBuilder;
	    jsonWriter : JSON.JSONByteArrayWriter;
	    widePayload : ARRAY[0..(LOG_JSON_PAYLOAD_MAX_SIZE / 2)] OF WORD;
	    rootIndex, objIndex : DINT;
	    i : UINT;
	    key : STRING(8);
	    init, prepared, converted, terminated : BOOL;
	    builderError : JSON.ERROR;
	    factoryErrorId : INT;
	    (* SetKeyWithValue needs variables: enumeration values as INT *)
	    levelValue, markerValue, typeValue : INT;
	    (* UTF-16 to UTF-8 encoding *)
	    wordIndex, byteIndex, wordCapacity, codePoint, nextWord, needed : UDINT;
	END_VAR

	IF NOT execute THEN
	    done := FALSE;
	    IF init THEN
	        jsonWriter(xExecute := FALSE, jsonData := jsonData^);
	        busy := jsonWriter.xBusy;
	    ELSE
	        busy := FALSE;
	    END_IF;
	    IF NOT busy THEN
	        prepared := FALSE; converted := FALSE;
	        error := FALSE; errorId := 0; payloadSize := 0;
	    END_IF;
	    RETURN;
	END_IF;

	(* Results stay until execute goes FALSE: the payload is converted only once *)
	IF error OR converted THEN RETURN; END_IF;
	done := FALSE; busy := TRUE;

	IF (logBufferSize = 0) OR (logBufferSize > LOG_APPENDER_BATCH_SIZE) OR NOT __ISVALIDREF(logBuffer) THEN
	    error := TRUE; errorId := 110; busy := FALSE;
	    RETURN;
	END_IF;

	(* One-time JSON data allocation *)
	IF NOT init THEN
	    jsonData := jsonFactory.Create(eError => factoryErrorId);
	    IF (factoryErrorId <> 0) OR (jsonData = 0) THEN
	        error := TRUE; errorId := 100; busy := FALSE;
	        RETURN;
	    END_IF;
	    init := TRUE;
	END_IF;

	(* Build the JSON data once per payload *)
	IF NOT prepared THEN
	    jsonData^.Clear();
	    jsonBuilder.Reset();
	    payloadSize := 0;
	    widePayload[LOG_JSON_PAYLOAD_MAX_SIZE / 2] := 0;
	    jsonBuilder(pJsonData := jsonData, diRootObj => rootIndex);
	    FOR i := 1 TO logBufferSize DO
	        key := RIGHT(CONCAT('000', UINT_TO_STRING(i)), 3);
	        objIndex := jsonBuilder.SetKeyWithObject(TO_WSTRING(key), diParentIndex := rootIndex, eError => builderError);
	        IF (TO_INT(builderError) <> 0) OR (objIndex < 0) THEN
	            error := TRUE; errorId := 111; busy := FALSE;
	            RETURN;
	        END_IF;
	        levelValue := TO_INT(logBuffer[i].level);
	        markerValue := TO_INT(logBuffer[i].marker);
	        typeValue := TO_INT(logBuffer[i].payloadType);
	        jsonBuilder.SetKeyWithValue("logEventId", logBuffer[i].logEventId, objIndex, eError => builderError);
	        IF TO_INT(builderError) = 0 THEN
	            jsonBuilder.SetKeyWithValue("logEventDate", logBuffer[i].logEventDate, objIndex, eError => builderError);
	        END_IF;
	        IF TO_INT(builderError) = 0 THEN
	            jsonBuilder.SetKeyWithValue("loggerName", logBuffer[i].loggerName, objIndex, eError => builderError);
	        END_IF;
	        IF TO_INT(builderError) = 0 THEN
	            jsonBuilder.SetKeyWithValue("source", logBuffer[i].source, objIndex, eError => builderError);
	        END_IF;
	        IF TO_INT(builderError) = 0 THEN
	            jsonBuilder.SetKeyWithValue("level", levelValue, objIndex, eError => builderError);
	        END_IF;
	        IF TO_INT(builderError) = 0 THEN
	            jsonBuilder.SetKeyWithValue("marker", markerValue, objIndex, eError => builderError);
	        END_IF;
	        IF TO_INT(builderError) = 0 THEN
	            jsonBuilder.SetKeyWithValue("type", typeValue, objIndex, eError => builderError);
	        END_IF;
	        IF TO_INT(builderError) = 0 THEN
	            jsonBuilder.SetKeyWithValue("repeatCount", logBuffer[i].repeatCount, objIndex, eError => builderError);
	        END_IF;
	        IF TO_INT(builderError) = 0 THEN
	            jsonBuilder.SetKeyWithValue("sequence", logBuffer[i].sequence, objIndex, eError => builderError);
	        END_IF;
	        IF TO_INT(builderError) = 0 THEN
	            CASE logBuffer[i].payloadType OF
	                LogPayloadType.Text:
	                    jsonBuilder.SetKeyWithValue("message", logBuffer[i].payload.message, objIndex, eError => builderError);
	                LogPayloadType.Enum:
	                    jsonBuilder.SetKeyWithValue("enumValue", logBuffer[i].payload.enumValue, objIndex, eError => builderError);
	                LogPayloadType.Numeric:
	                    jsonBuilder.SetKeyWithValue("numericValue", logBuffer[i].payload.numericValue, objIndex, eError => builderError);
	            END_CASE;
	        END_IF;
	        IF TO_INT(builderError) <> 0 THEN
	            error := TRUE; errorId := 111; busy := FALSE;
	            RETURN;
	        END_IF;
	    END_FOR;
	    prepared := TRUE;
	END_IF;

	(* JSON serialization into the UTF-16 buffer *)
	jsonWriter(xExecute := TRUE, xAsyncMode := asyncMode, wsLinebreak := lineBreak,
	    pwData := ADR(widePayload), udiSize := TO_UDINT(SIZEOF(widePayload)), jsonData := jsonData^);
	IF jsonWriter.xError THEN
	    error := TRUE; errorId := TO_INT(jsonWriter.eError); busy := FALSE;
	    IF errorId = 0 THEN errorId := 111; END_IF;
	    RETURN;
	END_IF;
	IF NOT jsonWriter.xDone THEN RETURN; END_IF;

	(* UTF-16 -> UTF-8, once; a lone surrogate becomes U+FFFD *)
	wordIndex := 0; byteIndex := 0; terminated := FALSE;
	wordCapacity := TO_UDINT(SIZEOF(widePayload)) / 2;
	WHILE wordIndex < wordCapacity DO
	    codePoint := WORD_TO_UDINT(widePayload[wordIndex]);
	    IF codePoint = 0 THEN terminated := TRUE; EXIT; END_IF;
	    wordIndex := wordIndex + 1;
	    IF (codePoint >= 16#D800) AND (codePoint <= 16#DBFF) THEN
	        IF wordIndex < wordCapacity THEN
	            nextWord := WORD_TO_UDINT(widePayload[wordIndex]);
	            IF (nextWord >= 16#DC00) AND (nextWord <= 16#DFFF) THEN
	                codePoint := 16#10000 + ((codePoint - 16#D800) * 1024) + (nextWord - 16#DC00);
	                wordIndex := wordIndex + 1;
	            ELSE
	                codePoint := 16#FFFD;
	            END_IF;
	        ELSE
	            codePoint := 16#FFFD;
	        END_IF;
	    ELSIF (codePoint >= 16#DC00) AND (codePoint <= 16#DFFF) THEN
	        codePoint := 16#FFFD;
	    END_IF;
	    IF codePoint <= 16#7F THEN needed := 1;
	    ELSIF codePoint <= 16#7FF THEN needed := 2;
	    ELSIF codePoint <= 16#FFFF THEN needed := 3;
	    ELSE needed := 4; END_IF;
	    (* Keep one byte for the terminator *)
	    IF byteIndex + needed > UINT_TO_UDINT(LOG_JSON_PAYLOAD_MAX_SIZE) THEN
	        error := TRUE; errorId := 112; payloadSize := 0; busy := FALSE;
	        RETURN;
	    END_IF;
	    CASE needed OF
	    1:
	        jsonPayload[byteIndex] := UDINT_TO_BYTE(codePoint);
	    2:
	        jsonPayload[byteIndex] := UDINT_TO_BYTE(16#C0 + (codePoint / 64));
	        jsonPayload[byteIndex + 1] := UDINT_TO_BYTE(16#80 + (codePoint MOD 64));
	    3:
	        jsonPayload[byteIndex] := UDINT_TO_BYTE(16#E0 + (codePoint / 4096));
	        jsonPayload[byteIndex + 1] := UDINT_TO_BYTE(16#80 + ((codePoint / 64) MOD 64));
	        jsonPayload[byteIndex + 2] := UDINT_TO_BYTE(16#80 + (codePoint MOD 64));
	    4:
	        jsonPayload[byteIndex] := UDINT_TO_BYTE(16#F0 + (codePoint / 262144));
	        jsonPayload[byteIndex + 1] := UDINT_TO_BYTE(16#80 + ((codePoint / 4096) MOD 64));
	        jsonPayload[byteIndex + 2] := UDINT_TO_BYTE(16#80 + ((codePoint / 64) MOD 64));
	        jsonPayload[byteIndex + 3] := UDINT_TO_BYTE(16#80 + (codePoint MOD 64));
	    END_CASE;
	    byteIndex := byteIndex + needed;
	END_WHILE;
	IF NOT terminated THEN
	    error := TRUE; errorId := 113; payloadSize := 0; busy := FALSE;
	    RETURN;
	END_IF;
	jsonPayload[byteIndex] := 0;
	payloadSize := byteIndex;
	converted := TRUE;
	done := TRUE;
	busy := FALSE;
	END_FUNCTION_BLOCK

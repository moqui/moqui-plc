FUNCTION_BLOCK MqttLogAppender
	
	VAR_INPUT
	    execute : BOOL;
	    (* Data sources *)
	    logBuffer : REFERENCE TO ARRAY[1..MoquiConf.LOG_MAX_SIZE] OF LogEvent;
	    logBufferSize : UINT;
	END_VAR
	VAR_OUTPUT
		done, busy, error : BOOL;
	    errorId : INT; (* 100 : ArgsErr *)
	END_VAR
	VAR
		pubTopic : WSTRING(1024) := MoquiConf.logTopic;
		(* Publisher *)
		publisher : MQTT.MQTTPublish;
		(* Publish properties v5 *)
		mqttPublishProperties : MQTT.MQTTPublishProperties := (
			bPayloadFormatIndicator := MoquiConf.pubPayloadFormatIndicator,
			wsContentType := MoquiConf.pubContentType,
			udiMessageExpiryInterval := MoquiConf.pubMessageExpiryInterval
			(* userProperties := pubUserProperties *)
		);
	    (* JSON serializer *)
	    logMapper : SerializeLogToJson;
	END_VAR

	IF NOT execute THEN
		logMapper(execute := FALSE, done => done, busy => busy,
			error => error, errorId => errorId);
	    publisher(xExecute := FALSE, mqttClient := ec.connectionFactory.connection, wsTopicName := pubTopic,
			xDone => done, xBusy => busy, xError => error, eMQTTError => errorId);
		RETURN;
	END_IF;

	(* Connect to the broker *)
	ec.connectionFactory(connect := TRUE, error => error, errorId => errorId);
	(* Reset and retry on next cycle *)
	IF ec.connectionFactory.error THEN
		ec.connectionFactory(connect := FALSE, error => error, errorId => errorId);
		done := FALSE; busy := FALSE;
		RETURN;
	END_IF;

	(* Waiting for connection to broker *)
	IF NOT ec.connectionFactory.connected THEN RETURN; END_IF;

	IF NOT publisher.xBusy THEN
		(* JSON mapping *)
		logMapper(execute := TRUE, logBuffer := logBuffer, logBufferSize := logBufferSize,
			lineBreak := "", (* compact output: avoid WSTRING line-break embedding null bytes in byte array *)
			busy => busy, error => error, errorId => errorId);
		IF logMapper.error THEN
			(* Reset JSON writer *)
			logMapper(execute := FALSE, busy => busy,
				error => error, errorId => errorId);
			done := FALSE; busy := FALSE;
			RETURN;
		END_IF;
	END_IF;

	IF logMapper.done THEN
		(* Publish the payload *)
		publisher(xExecute := TRUE, mqttClient := ec.connectionFactory.connection, wsTopicName := pubTopic,
			pbPayload := ADR(logMapper.jsonPayload), udiPayloadSize := logMapper.payloadSize,
			eQoS := MoquiConf.logPubQoS, xReDelivery := MoquiConf.logReDelivery, xRetain := MoquiConf.logPubRetain,
			udiTimeOut := UINT_TO_UDINT(MoquiConf.logAppenderTimeout), mQTTPublishProperties := mqttPublishProperties,
			xDone => done, xBusy => busy, xError => error, eMQTTError => errorId);
	END_IF;
	END_FUNCTION_BLOCK

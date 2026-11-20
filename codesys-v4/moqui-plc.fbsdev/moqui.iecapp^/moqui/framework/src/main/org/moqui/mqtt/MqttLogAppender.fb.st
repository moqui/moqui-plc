(*
 * Publishes one batch of log records as one MQTT message on logTopic.
 *
 * The broker connection belongs to MqttCommunication: this block only uses connectionFactory.connection.
 * A rising execute serializes the batch and publishes it; several steps run in the same call when they can.
 * done or error stay set until execute goes FALSE; then call the block until busy is FALSE before the next batch,
 * because the publisher and the JSON writer may still use the payload memory.
 *
 * errorId: 200 not connected to the broker; 100-113 serialization (SerializeLogToJson, serializeError = TRUE);
 * otherwise the MQTT error of the publisher (201 when the publisher reports an error without a code).
 *)
FUNCTION_BLOCK MqttLogAppender
	
	VAR_INPUT
	    execute : BOOL;
	    (* Data sources *)
	    logBuffer : REFERENCE TO ARRAY[1..MoquiConf.LOG_APPENDER_BATCH_SIZE] OF LogEvent;
	    logBufferSize : UINT;
	    (* The same batch was already sent once: set the DUP flag (QoS 1/2 only) *)
	    redelivery : BOOL;
	END_VAR
	VAR_OUTPUT
		done, busy, error : BOOL;
	    errorId : INT;
	    (* The error comes from the JSON serialization: a smaller batch may fit *)
	    serializeError : BOOL;
	END_VAR
	VAR
		state : MqttLogAppenderStatus := MqttLogAppenderStatus.Idle;
		finished : BOOL;
		pubTopic : WSTRING(1024) := MoquiConf.logTopic;
		(* Publisher *)
		publisher : MQTT.MQTTPublish;
		(* Publish properties v5 *)
		mqttPublishProperties : MQTT.MQTTPublishProperties := (
			bPayloadFormatIndicator := MoquiConf.pubPayloadFormatIndicator,
			wsContentType := MoquiConf.pubContentType,
			udiMessageExpiryInterval := MoquiConf.logMessageExpiryInterval
			(* userProperties := pubUserProperties *)
		);
	    (* JSON serializer *)
	    logMapper : SerializeLogToJson;
	END_VAR

	IF NOT execute THEN
		(* Release the JSON writer and the publisher; the payload stays untouched while either is busy *)
		logMapper(execute := FALSE);
		publisher(xExecute := FALSE, mqttClient := ec.connectionFactory.connection, wsTopicName := pubTopic);
		busy := logMapper.busy OR publisher.xBusy;
		done := FALSE;
		IF NOT busy THEN
			error := FALSE; errorId := 0; serializeError := FALSE;
			finished := FALSE;
			state := MqttLogAppenderStatus.Idle;
		END_IF;
		RETURN;
	END_IF;

	(* Outputs of the finished batch stay until execute goes FALSE *)
	IF finished THEN RETURN; END_IF;
	busy := TRUE;

	IF state = MqttLogAppenderStatus.Idle THEN
		IF NOT ec.connectionFactory.connected THEN
			error := TRUE; errorId := 200;
			busy := FALSE; finished := TRUE;
			RETURN;
		END_IF;
		state := MqttLogAppenderStatus.Serialize;
	END_IF;

	IF state = MqttLogAppenderStatus.Serialize THEN
		(* Compact output: no line breaks in the payload *)
		logMapper(execute := TRUE, logBuffer := logBuffer, logBufferSize := logBufferSize, lineBreak := "");
		IF logMapper.error THEN
			error := TRUE; errorId := logMapper.errorId; serializeError := TRUE;
			busy := FALSE; finished := TRUE;
			RETURN;
		ELSIF logMapper.done THEN
			state := MqttLogAppenderStatus.Publish;
		END_IF;
	END_IF;

	IF state = MqttLogAppenderStatus.Publish THEN
		publisher(xExecute := TRUE, mqttClient := ec.connectionFactory.connection, wsTopicName := pubTopic,
			pbPayload := ADR(logMapper.jsonPayload), udiPayloadSize := logMapper.payloadSize,
			eQoS := MoquiConf.logPubQoS, xReDelivery := redelivery AND (MoquiConf.logPubQoS <> MQTT.MQTT_QOS.QoS0),
			xRetain := MoquiConf.logPubRetain, udiTimeOut := MoquiConf.logAppenderTimeout,
			mQTTPublishProperties := mqttPublishProperties);
		IF publisher.xError THEN
			error := TRUE; errorId := TO_INT(publisher.eMQTTError);
			IF errorId = 0 THEN errorId := 201; END_IF;
			busy := FALSE; finished := TRUE;
		ELSIF publisher.xDone THEN
			done := TRUE;
			busy := FALSE; finished := TRUE;
		END_IF;
	END_IF;
	END_FUNCTION_BLOCK

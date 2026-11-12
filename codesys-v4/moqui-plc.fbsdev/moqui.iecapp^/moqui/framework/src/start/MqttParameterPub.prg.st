(*
 * Optional publisher for parameter replication between peer PLCs/Applications,
 * typically for a developer-defined redundancy strategy. Operational numeric
 * and textual telemetry is published by LogDispatcher instead.
 *)
PROGRAM MqttParameterPub
	
	VAR
		done, busy, error : BOOL;
	    errorId : INT;
		jsonPayload : WSTRING(MoquiConf.JSON_PAYLOAD_MAX_SIZE);
		pubTopic : WSTRING(1024) := MoquiConf.liveParamsPubTopic;
		pubMessage : STRING(MoquiConf.JSON_PAYLOAD_MAX_SIZE);
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
	    parameterMapper : SerializeParametersToJson;
	END_VAR

	(* Publishing disabled *)
	IF NOT ec.paramsPubEnable THEN
		done := FALSE; busy := FALSE; error := FALSE; errorId := 0;
		RETURN;
	END_IF;

	(* Connect to the broker *)
	ec.connectionFactory(connect := TRUE, error => error, errorId => errorId);
	(* Reset and retry on next cycle *)
	IF ec.connectionFactory.connection.xError THEN
		ec.connectionFactory(connect := FALSE, error => error, errorId => errorId);
		done := FALSE; busy := FALSE;
		RETURN;
	END_IF;

	(* Waiting for connection to broker *)
	IF NOT ec.connectionFactory.connected THEN RETURN; END_IF;

	IF NOT publisher.xBusy THEN
		(* JSON mapping *)
		parameterMapper(execute := TRUE, jsonPayload => jsonPayload,
			busy => busy, error => error, errorId => errorId);
		IF parameterMapper.error THEN
			(* Reset JSON writer *)
			parameterMapper(execute := FALSE, error => error, errorId => errorId);
			done := FALSE; busy := FALSE;
			RETURN;
		END_IF;
	END_IF;

	IF parameterMapper.done THEN
		(* Publish the payload *)
		pubMessage := TO_STRING(jsonPayload);
		publisher(xExecute := TRUE, mqttClient := ec.connectionFactory.connection, wsTopicName := pubTopic,
			pbPayload := ADR(pubMessage), udiPayloadSize := INT_TO_UDINT(LEN(pubMessage)),
			eQoS := MoquiConf.paramsPubQoS, xReDelivery := MoquiConf.paramsReDelivery, xRetain := MoquiConf.paramsPubRetain,
			udiTimeOut := MoquiConf.liveParamsPubTimeout, mQTTPublishProperties := mqttPublishProperties,
			xDone => done, xBusy => busy, xError => error, eMQTTError => errorId);

		IF publisher.xError OR publisher.xDone THEN
			(* Auto reset: next cycle restarts from scratch *)
			parameterMapper(execute := FALSE, busy => busy,
				error => error, errorId => errorId);
			publisher(xExecute := FALSE, mqttClient := ec.connectionFactory.connection, wsTopicName := pubTopic,
				xDone => done, xBusy => busy, xError => error, eMQTTError => errorId);
		END_IF;
	END_IF;
	END_PROGRAM

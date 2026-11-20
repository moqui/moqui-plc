(*
 * Live parameter writes from Moqui: subscribes liveParamsSubTopic and applies each payload with
 * DeserializeJsonToParameters. Called by MqttCommunication, which owns the broker connection.
 *)
PROGRAM MqttParameterSub
	
	VAR
		done, busy, error : BOOL;
	    errorId : INT;
		(* Subscriber *)
		subscriber : MQTT.MQTTSubscribe;
		(* Subscribe properties v5 *)
		mqttSubscribeProperties : MQTT.MQTTSubscribeProperties := (
			udiSubscriptionIdentifier := MoquiConf.subscriptionIdentifier,
			xNoLocalOption := MoquiConf.subNoLocalOption,
			xRetainAsPublished := MoquiConf.subRetainAsPublished,
			eRetainHandling := MoquiConf.subRetainHandling
			(* userProperties := subUserProperties; *)
		);
	    (* JSON parser *)
	    parser : DeserializeJsonToParameters;
		parserActive : BOOL; (* TRUE while parser is running across multiple cycles *)
		subTopicFilter : WSTRING(1024) := MoquiConf.liveParamsSubTopic;
		(* Last incoming message *)
		rxBuffer : STRING(MoquiConf.JSON_PAYLOAD_MAX_SIZE);
		pRxBytes : POINTER TO ARRAY[0..MoquiConf.JSON_PAYLOAD_MAX_SIZE] OF BYTE;
		clearIdx : UINT;
		lastSubMessage : STRING(MoquiConf.JSON_PAYLOAD_MAX_SIZE);
	    receivedPayload : WSTRING(MoquiConf.JSON_PAYLOAD_MAX_SIZE);
		subscriberEnable : BOOL;
	END_VAR

	(* Subscription disabled *)
	IF NOT ec.paramsSubEnable THEN
		subscriber(xEnable := FALSE, mqttClient := ec.connectionFactory.connection, wsTopicFilter := subTopicFilter);
		parser(execute := FALSE);
		parserActive := FALSE;
		done := FALSE; busy := FALSE; error := FALSE; errorId := 0;
	    RETURN;
	END_IF;

	(* Manage subscriber enable: disable for one cycle on error to reset the FB *)
	IF subscriber.xError THEN
		subscriberEnable := FALSE;
	ELSE
		subscriberEnable := ec.connectionFactory.connected;
	END_IF;

	(* Drive subscriber continuously; xDone = subscription confirmed (sub ack), not end of session *)
	subscriber(xEnable := subscriberEnable, mqttClient := ec.connectionFactory.connection,
		eFilterMode := MoquiConf.paramsSubFilterMode, wsTopicFilter := subTopicFilter, eSubscribeQoS := MoquiConf.paramsSubQoS,
		udiTimeout := MoquiConf.liveParamsSubTimeout, pbPayload := ADR(rxBuffer),
		udiMaxPayloadSize := SIZEOF(rxBuffer) - 1, mQTTSubscribeProperties := mqttSubscribeProperties,
		xDone => done, xBusy => busy, xError => error, eMQTTError => errorId);

	(* xReceived pulses TRUE for one cycle only: copy NUL-terminated buffer, clear rxBuffer, and latch parserActive *)
	IF subscriber.xReceived THEN
		IF subscriber.xSubscribeActive AND subscriber.wsLastTopic = subTopicFilter THEN
			lastSubMessage := rxBuffer;
			receivedPayload := TO_WSTRING(lastSubMessage);
			IF parserActive THEN
				parser(execute := FALSE);
			END_IF;
			parserActive := TRUE;
		END_IF;
		pRxBytes := ADR(rxBuffer);
		FOR clearIdx := 0 TO MoquiConf.JSON_PAYLOAD_MAX_SIZE DO
			IF pRxBytes^[clearIdx] = 0 THEN
				EXIT;
			END_IF;
			pRxBytes^[clearIdx] := 0;
		END_FOR;
	END_IF;

	(* Drive parser every cycle until done/error, regardless of xReceived *)
	IF parserActive THEN
		(* JSON parsing *)
		parser(execute := TRUE, jsonPayload := receivedPayload,
			busy => busy, error => error, errorId => errorId);

		IF parser.done OR parser.error THEN
			(* Auto reset: next cycle restarts from scratch *)
			parser(execute := FALSE, done => done, busy => busy,
				error => error, errorId => errorId);
			parserActive := FALSE;
		END_IF;
	END_IF;
	END_PROGRAM

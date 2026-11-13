(*
 * MQTT communication task program: the only caller of the shared connectionFactory.
 *
 * Every cycle it services the broker connection, then the programs that use it, in this order:
 *   1. MqttParameterSub: live parameter writes from Moqui, applied first so that a queued log batch never delays them;
 *   2. MqttParameterPub: optional peer-PLC parameter replication (paramsPubEnable, FALSE by default);
 *   3. LogDispatcher: the log batches (logAppenderEnable).
 * One task owns the MQTT client and all its function blocks, so no other task calls them concurrently.
 *
 * After a connection error the client is disabled, which resets it, and enabled again after mqttReconnectDelay.
 * The connection is opened only while at least one of the three programs is enabled.
 *)
PROGRAM MqttCommunication
	
	VAR
		connect : BOOL := TRUE;
		reconnectTimer : TON;
		(* Connection errors since start *)
		connectionErrorCount : UDINT;
	END_VAR

	(* An error of the previous cycle disables the client for mqttReconnectDelay *)
	IF connect AND ec.connectionFactory.error THEN
		connect := FALSE;
		IF connectionErrorCount < 16#FFFFFFFF THEN connectionErrorCount := connectionErrorCount + 1; END_IF;
	END_IF;
	reconnectTimer(IN := NOT connect, PT := MoquiConf.mqttReconnectDelay);
	IF reconnectTimer.Q THEN connect := TRUE; END_IF;

	ec.connectionFactory(connect := connect AND (ec.logAppenderEnable OR ec.paramsPubEnable OR ec.paramsSubEnable));

	MqttParameterSub();
	MqttParameterPub();
	LogDispatcher();
	END_PROGRAM

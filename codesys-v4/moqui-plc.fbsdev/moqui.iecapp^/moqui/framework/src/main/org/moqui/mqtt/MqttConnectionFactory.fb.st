(* Component to connect with a MQTT broker, using default configurations. *)
FUNCTION_BLOCK MqttConnectionFactory
	
	VAR_INPUT
		connect : BOOL := TRUE;
	END_VAR
	VAR_OUTPUT
		connection : MQTT.MQTTClient;
	    connected : BOOL;
	    busy : BOOL;
	    error : BOOL;
		errorId : INT;
	END_VAR
	VAR
		(* Connect properties v5 *)
		mqttConnectProperties : MQTT.MQTTConnectProperties := (
			udiSessionExpiryInterval := MoquiConf.sessionExpiryInterval,
			udiMaximumPacketSize := MoquiConf.maximumPacketSize
			(* userProperties := connectUserProperties *)
		);
		(* Will properties v5 *)
		mqttWillProperties : MQTT.MQTTWillProperties := (
			bPayloadFormatIndicator := MoquiConf.willPayloadFormatIndicator,
			udiMessageExpiryInterval := MoquiConf.willMessageExpiryInterval,
			wsContentType := MoquiConf.willContentType,
			udiWillDelayInterval := MoquiConf.willDelayInterval
			(* userProperties := willUserProperties *)
	    );
		(* TLS context *)
		cipherList : NBS.CIPHER_LIST := (psList := ADR('HIGH'), udiSize := 5);
		commonName : STRING := 'moqui';
	    certInfo : NBS.CERT_INFO := (psInfo := ADR(commonName), udiSize := INT_TO_UDINT(LEN(commonName)));
		defaultTlsContext : NBS.TLSContext := (
			sUseCaseName := commonName,
			ePurpose := NBS.PURPOSE.CLIENT_SIDE,
			sTLSVersion := '1.3',
			sCipherList := cipherList,
			sHostname := MoquiConf.brokerUrl,
			ciCertInfo := certInfo,
			udiVerificationMode	:= 2, (* 1 => No peer verification, 2 => Active Peer verification *)
			itfCertVerifer := 0
		);
		nullTlsContext : NBS.ITLSContext := 0;
		tlsContext : NBS.ITLSContext;
		useTLS : BOOL := FALSE;

		(* 
	     * To use client certificates, configure the connection via the TLS context.
		 * Example:
		 *      commonName : STRING := 'COMMON_NAME_OF_CERTIFICATE'; // CN of the certificate (common name). 
		 *      cipherList : NBS.CIPHER_LIST := (psList := ADR('HIGH'), udiSize := 5); // Cipher string see https://www.openssl.org/docs/man1.1.1/man1/ciphers.html
		 *      certInfo : NBS.CERT_INFO := (psInfo := ADR(commonName), udiSize := SIZEOF(commonName)); // CN of the certificate (common name)
		 *      tlsContext : NBS.TLSContext := (
		 *          sUseCaseName := commonName, // A certificate is stored in the certificate store with the use case name.
		 *          ePurpose := NBS.PURPOSE.CLIENT_SIDE, // For client certificates set this to NBS.PURPOSE.CLIENT_SIDE
	     *          sTLSVersion := '1.3', // The TLS version
	     *          sCipherList := cipherList, // Set the cipher list
	     *          sHostname := brokerUrl, // The hostname of the broker
	     *          udiVerificationMode := 2, // 2 => Active Peer verification
	     *          ciCertInfo := certInfo, // Set the cert info
	     *          itfCertVerifer := 0); // 0 => No Verifier 
		 *      client : MQTT.MQTTClient := (itfTLSCOntext := _tlsContext);
		 * Use the method TLSContext.SetInitialValue to set the context while runtime and set the context via the input itfTLSCOntext of the client FB.
		 *)
	END_VAR

	(* TLS selection *)
	tlsContext := nullTlsContext;
	IF useTLS THEN tlsContext := defaultTlsContext; END_IF;

	(* Configure the MQTT connection *)
	connection(xEnable := connect, xConnectedToBroker => connected, xError => error, eMQTTerror => errorId,
		sHostname := MoquiConf.brokerUrl, uiPort := MoquiConf.brokerPort, sWebSocketUrl := MoquiConf.webSocketUrl, sClientId := MoquiConf.clientId,
		itfTLSContext := tlsContext, eCommunicationMode := MoquiConf.communicationMode, eMQTTVersion := MoquiConf.mqttVersion,
		wsUsername := MoquiConf.username, wsPassword := MoquiConf.password, mQTTConnectProperties := mqttConnectProperties,
		uiKeepAlive := MoquiConf.keepAlive, xCleanSession := MoquiConf.cleanSession, udiTimeOut := MoquiConf.timeout, tPingInterval := MoquiConf.pingInterval,
		wsWillTopic := MoquiConf.willTopic, pbWillMessage := ADR(MoquiConf.willMessage), uiWillMessageSize := INT_TO_UINT(LEN(MoquiConf.willMessage)),
		xWillRetain := MoquiConf.willRetain, eWillQoS := MoquiConf.willQoS, mQTTWillProperties := mqttWillProperties);
	END_FUNCTION_BLOCK

(*
 * Current UTC time in milliseconds since 1970-01-01 (high resolution RTC).
 * Used to build unique log event IDs: the value separates restarts of the application.
 * Returns 0 if the RTC cannot be read.
 *)
FUNCTION nowMillis : ULINT
	VAR
	    timestamp : SysTimeRtc.SYSTIME;
	    result : SysTimeRtc.RTS_IEC_RESULT;
	END_VAR

	result := SysTimeRtcHighResGet(pTimestamp := timestamp);
	IF result <> 0 THEN RETURN; END_IF;
	nowMillis := timestamp;
END_FUNCTION

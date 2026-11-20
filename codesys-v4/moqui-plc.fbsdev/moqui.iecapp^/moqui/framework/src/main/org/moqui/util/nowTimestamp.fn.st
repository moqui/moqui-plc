(*
 * Current date and time in UTC, from the real-time clock.
 * Log events carry UTC: the gateway reads a DT# date as UTC, and UTC has no repeated hour at the daylight
 * saving change. Convert to local time only for display.
 * Returns DT#1970-01-01-00:00:00 if the RTC cannot be read.
 *)
FUNCTION nowTimestamp : DATE_AND_TIME
	VAR
	    utcTimestamp : UDINT;
	    result : SysTimeRtc.RTS_IEC_RESULT;
	END_VAR

	(* Seconds since 1970-01-01 in UTC *)
	utcTimestamp := SysTimeRtcGet(result);
	IF result <> 0 THEN RETURN; END_IF;
	nowTimestamp := TO_DT(utcTimestamp);
	END_FUNCTION

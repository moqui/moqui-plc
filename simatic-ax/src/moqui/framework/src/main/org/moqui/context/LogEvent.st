TYPE LogEvent : STRUCT
	(* Unique identifier for the log event *)
    logEventId : STRING;
    loggerName : STRING;
	marker : LogMarker;
    level : LogLevel;
    logEventDate : DATE_AND_TIME;
	source : STRING;
	payloadType : LogPayloadType;
    payload : LogPayload;
	(* contextData: STRING; *)
	(*
	 * Occurrences this record stands for: 1 for an event, N for the summary that LoggerFacade writes when the
	 * same event was repeated N more times inside the suppression window ("last message repeated N times").
	 *)
    repeatCount : UINT;
	(* Position of the record in its LogRingBuffer, set by the buffer: consecutive records of one source differ by 1. *)
	sequence : UDINT;
END_STRUCT; END_TYPE

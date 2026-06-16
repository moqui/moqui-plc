TYPE LogSource : STRUCT
	(* Reference to log ring buffer *)
    logRef : REF_TO LogRingBuffer;
	lastLogSize : UINT;
	lastHead : UINT := UINT#1;
	lastTail : UINT := UINT#1;
	lastOverflowCount : UDINT;
END_STRUCT; END_TYPE

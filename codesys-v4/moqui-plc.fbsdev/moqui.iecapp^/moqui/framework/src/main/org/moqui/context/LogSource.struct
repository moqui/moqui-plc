(*
 * One registered LoggerFacade buffer, as seen by LogDispatcher.
 * LoggerFacade sets logRef once; every other field belongs to LogDispatcher, the only consumer.
 *)
TYPE LogSource : STRUCT
	(* Reference to log ring buffer *)
    logRef : REFERENCE TO LogRingBuffer;
	(* Slot of the oldest record not yet released by LogDispatcher *)
	readSlot : UINT := 1;
	(* LogRingBuffer.droppedCount already reported in a published "log events dropped" record *)
	reportedDropCount : UDINT;
	(* Records published, and records discarded after logPublishMaxAttempts failed attempts *)
	publishedCount : UDINT;
	discardedCount : UDINT;
END_STRUCT END_TYPE

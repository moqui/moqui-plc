(*
 * One registered LoggerFacade buffer, as seen by its consumer.
 * LoggerFacade sets logRef once; every other field belongs to the consumer. The AX port has no MQTT consumer yet
 * (the intended Siemens path is OPC UA): a future consumer follows LogDispatcher of the canonical IEC source.
 *)
TYPE LogSource : STRUCT
	(* Reference to log ring buffer *)
    logRef : REF_TO LogRingBuffer;
	(* Slot of the oldest record not yet released by the consumer *)
	readSlot : UINT := UINT#1;
	(* LogRingBuffer.droppedCount already reported by the consumer *)
	reportedDropCount : UDINT;
	(* Records published, and records discarded by the consumer *)
	publishedCount : UDINT;
	discardedCount : UDINT;
END_STRUCT; END_TYPE

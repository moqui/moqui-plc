(* CODESYS __XADD operator used by moqui-plc, as an interface declaration only (no
 * implementation). scripts/st_dialect.py writes each __XADD call as MOQUI_XADD.
 * A Rust runtime maps it to an atomic fetch-add with sequentially consistent
 * ordering: it adds diValue to the DINT at pAddend and returns the previous value.
 * LoggerFacade, LogRingBuffer and LogDispatcher use it to exchange the counters of
 * the log buffers between the control tasks and the communication task.
 *)

FUNCTION MOQUI_XADD : DINT
VAR_INPUT
    pAddend : POINTER TO DINT;
    diValue : DINT;
END_VAR
RETURN;
END_FUNCTION

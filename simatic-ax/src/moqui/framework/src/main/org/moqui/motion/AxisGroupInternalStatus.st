(* Internal FSM state. Not exposed to callers.
   UINT base type with BaseType-first form so >= ordering compiles in SIMATIC AX. *)
TYPE AxisGroupInternalStatus : UINT
    ( NotPowered              := UINT#0
    , Enabling                := UINT#1
    , Standby                 := UINT#2
    , MoveLinearAbsoluteState := UINT#3
    , CheckLinearAbsoluteState  := UINT#4
    , MoveLinearRelativeState   := UINT#5
    , CheckLinearRelativeState  := UINT#6
    , MoveCircularAbsoluteState  := UINT#7
    , CheckCircularAbsoluteState := UINT#8
    , MoveCircularRelativeState  := UINT#9
    , CheckCircularRelativeState := UINT#10
    , MoveDirectAbsoluteState    := UINT#11
    , CheckDirectAbsoluteState   := UINT#12
    , MoveDirectRelativeState    := UINT#13
    , CheckDirectRelativeState   := UINT#14
    , HaltState      := UINT#15
    , StoppingState  := UINT#16
    , WaitReset      := UINT#17
    , Error          := UINT#18
    ) := UINT#0; END_TYPE

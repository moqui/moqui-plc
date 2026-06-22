(* Compile-only compatibility stubs for Motion profile.
   Provides CODESYS Motion namespace types and MC_ function-block shells
   that Axis.st references.  No runtime logic here. *)

NAMESPACE Motion

    TYPE
        MC_BUFFER_MODE : USINT
            ( aborting      := USINT#0
            , buffered      := USINT#1
            , blendingLow   := USINT#2
            , blendingPrev  := USINT#3
            , blendingNext  := USINT#4
            , blendingHigh  := USINT#5 ) := USINT#0;

        (* IEC-61131-3 is case-insensitive: MC_Direction = MC_DIRECTION *)
        MC_Direction : USINT
            ( positive         := USINT#1
            , negative         := USINT#2
            , currentDirection := USINT#3
            , shortest         := USINT#4 ) := USINT#1;

        MC_STARTMODE : USINT
            ( absolute  := USINT#0
            , relative  := USINT#1
            , additive  := USINT#2 ) := USINT#0;

        MC_CAM_ID : STRUCT
            value : DWORD;
        END_STRUCT;

        AXIS_REF_SM3 : STRUCT
            dummy : BOOL;
        END_STRUCT;

        TRIGGER_REF : STRUCT
            dummy : BOOL;
        END_STRUCT;

        MC_TP_REF : STRUCT
            dummy : BOOL;
        END_STRUCT;

        MC_TV_REF : STRUCT
            dummy : BOOL;
        END_STRUCT;

        MC_TA_REF : STRUCT
            dummy : BOOL;
        END_STRUCT;
    END_TYPE

END_NAMESPACE

(* Axis object reference used as VAR_IN_OUT in Axis.st *)
TYPE
    TO_SynchronousAxis : STRUCT
        wDriveId : WORD;
        dummy    : BOOL;
    END_STRUCT;
END_TYPE

FUNCTION TO_STRING : STRING
VAR_INPUT
    value : WORD;
END_VAR
    TO_STRING := System.Strings.ToString(value);
END_FUNCTION

FUNCTION_BLOCK MC_Power
VAR_IN_OUT
    Axis            : TO_SynchronousAxis;
END_VAR
VAR_INPUT
    Enable          : BOOL;
    EnablePositive  : BOOL;
    EnableNegative  : BOOL;
    bRegulatorOn    : BOOL;
    bDriveStart     : BOOL;
END_VAR
VAR_OUTPUT
    Status  : BOOL;
    Busy    : BOOL;
    Error   : BOOL;
    ErrorID : DWORD;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_Reset
VAR_IN_OUT
    Axis    : TO_SynchronousAxis;
END_VAR
VAR_INPUT
    Execute : BOOL;
END_VAR
VAR_OUTPUT
    Done    : BOOL;
    Busy    : BOOL;
    Error   : BOOL;
    ErrorID : DWORD;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_SetPosition
VAR_IN_OUT
    Axis     : TO_SynchronousAxis;
END_VAR
VAR_INPUT
    Execute  : BOOL;
    Position : LREAL;
    Mode     : BOOL;
END_VAR
VAR_OUTPUT
    Done    : BOOL;
    Busy    : BOOL;
    Error   : BOOL;
    ErrorID : DWORD;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_Home
VAR_IN_OUT
    Axis       : TO_SynchronousAxis;
END_VAR
VAR_INPUT
    Execute    : BOOL;
    Position   : LREAL;
    HomingMode : INT;
END_VAR
VAR_OUTPUT
    Done           : BOOL;
    Busy           : BOOL;
    CommandAborted : BOOL;
    Error          : BOOL;
    ErrorID        : DWORD;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_MoveVelocity
VAR_IN_OUT
    Axis         : TO_SynchronousAxis;
END_VAR
VAR_INPUT
    Execute      : BOOL;
    Velocity     : REAL;
    Acceleration : REAL;
    Deceleration : REAL;
    Jerk         : REAL;
    Direction    : Motion.MC_Direction;
    BufferMode   : Motion.MC_BUFFER_MODE;
END_VAR
VAR_OUTPUT
    InVelocity     : BOOL;
    Busy           : BOOL;
    CommandAborted : BOOL;
    Error          : BOOL;
    ErrorID        : DWORD;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_MoveAbsolute
VAR_IN_OUT
    Axis         : TO_SynchronousAxis;
END_VAR
VAR_INPUT
    Execute      : BOOL;
    Position     : REAL;
    Velocity     : REAL;
    Acceleration : REAL;
    Deceleration : REAL;
    Jerk         : REAL;
    Direction    : Motion.MC_Direction;
    BufferMode   : Motion.MC_BUFFER_MODE;
END_VAR
VAR_OUTPUT
    Done           : BOOL;
    Busy           : BOOL;
    CommandAborted : BOOL;
    Error          : BOOL;
    ErrorID        : DWORD;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_MoveRelative
VAR_IN_OUT
    Axis         : TO_SynchronousAxis;
END_VAR
VAR_INPUT
    Execute      : BOOL;
    Distance     : REAL;
    Velocity     : REAL;
    Acceleration : REAL;
    Deceleration : REAL;
    Jerk         : REAL;
    BufferMode   : Motion.MC_BUFFER_MODE;
END_VAR
VAR_OUTPUT
    Done           : BOOL;
    Busy           : BOOL;
    CommandAborted : BOOL;
    Error          : BOOL;
    ErrorID        : DWORD;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_MoveAdditive
VAR_IN_OUT
    Axis         : TO_SynchronousAxis;
END_VAR
VAR_INPUT
    Execute      : BOOL;
    Distance     : REAL;
    Velocity     : REAL;
    Acceleration : REAL;
    Deceleration : REAL;
    Jerk         : REAL;
    BufferMode   : Motion.MC_BUFFER_MODE;
END_VAR
VAR_OUTPUT
    Done           : BOOL;
    Busy           : BOOL;
    CommandAborted : BOOL;
    Error          : BOOL;
    ErrorID        : DWORD;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_MoveSuperImposed
VAR_IN_OUT
    Axis             : TO_SynchronousAxis;
END_VAR
VAR_INPUT
    Execute          : BOOL;
    Distance         : REAL;
    VelocityDiff     : REAL;
    Acceleration     : REAL;
    Deceleration     : REAL;
    Jerk             : REAL;
    AccelerationDiff : REAL;
    DecelerationDiff : REAL;
    JerkDiff         : REAL;
    BufferMode       : Motion.MC_BUFFER_MODE;
END_VAR
VAR_OUTPUT
    Done           : BOOL;
    Busy           : BOOL;
    CommandAborted : BOOL;
    Error          : BOOL;
    ErrorID        : DWORD;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_Halt
VAR_IN_OUT
    Axis         : TO_SynchronousAxis;
END_VAR
VAR_INPUT
    Execute      : BOOL;
    Deceleration : REAL;
    Jerk         : REAL;
    BufferMode   : Motion.MC_BUFFER_MODE;
END_VAR
VAR_OUTPUT
    Done           : BOOL;
    Busy           : BOOL;
    CommandAborted : BOOL;
    Error          : BOOL;
    ErrorID        : DWORD;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_HaltSuperImposed
VAR_IN_OUT
    Axis         : TO_SynchronousAxis;
END_VAR
VAR_INPUT
    Execute      : BOOL;
    Deceleration : REAL;
    Jerk         : REAL;
END_VAR
VAR_OUTPUT
    Done           : BOOL;
    Busy           : BOOL;
    CommandAborted : BOOL;
    Error          : BOOL;
    ErrorID        : DWORD;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_Stop
VAR_IN_OUT
    Axis         : TO_SynchronousAxis;
END_VAR
VAR_INPUT
    Execute      : BOOL;
    Deceleration : REAL;
    Jerk         : REAL;
END_VAR
VAR_OUTPUT
    Done    : BOOL;
    Busy    : BOOL;
    Error   : BOOL;
    ErrorID : DWORD;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_Jog
VAR_IN_OUT
    Axis         : TO_SynchronousAxis;
END_VAR
VAR_INPUT
    JogForward   : BOOL;
    JogBackward  : BOOL;
    Velocity     : REAL;
    Acceleration : REAL;
    Deceleration : REAL;
    Jerk         : REAL;
END_VAR
VAR_OUTPUT
    Busy    : BOOL;
    Error   : BOOL;
    ErrorID : DWORD;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_SetOverride
VAR_IN_OUT
    Axis       : TO_SynchronousAxis;
END_VAR
VAR_INPUT
    Enable     : BOOL;
    VelFactor  : REAL;
    AccFactor  : REAL;
    JerkFactor : REAL;
END_VAR
VAR_OUTPUT
    Enabled : BOOL;
    Busy    : BOOL;
    Error   : BOOL;
    ErrorID : DWORD;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_GearIn
VAR_IN_OUT
    Slave            : TO_SynchronousAxis;
END_VAR
VAR_INPUT
    Master           : REF_TO Motion.AXIS_REF_SM3;
    Execute          : BOOL;
    RatioNumerator   : DINT;
    RatioDenominator : UDINT;
    Acceleration     : REAL;
    Deceleration     : REAL;
    Jerk             : REAL;
    BufferMode       : Motion.MC_BUFFER_MODE;
END_VAR
VAR_OUTPUT
    InSync         : BOOL;
    InGear         : BOOL;
    Busy           : BOOL;
    CommandAborted : BOOL;
    Error          : BOOL;
    ErrorID        : DWORD;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_GearInPos
VAR_IN_OUT
    Slave               : TO_SynchronousAxis;
END_VAR
VAR_INPUT
    Master              : REF_TO Motion.AXIS_REF_SM3;
    Execute             : BOOL;
    RatioNumerator      : DINT;
    RatioDenominator    : DINT;
    MasterSyncPosition  : LREAL;
    SlaveSyncPosition   : LREAL;
    SyncMode            : USINT;
    Velocity            : REAL;
    Acceleration        : REAL;
    Deceleration        : REAL;
    Jerk                : REAL;
    BufferMode          : Motion.MC_BUFFER_MODE;
    StartMode           : Motion.MC_STARTMODE;
END_VAR
VAR_OUTPUT
    InSync         : BOOL;
    Busy           : BOOL;
    CommandAborted : BOOL;
    Error          : BOOL;
    ErrorID        : DWORD;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_GearOut
VAR_IN_OUT
    Slave   : TO_SynchronousAxis;
END_VAR
VAR_INPUT
    Execute : BOOL;
END_VAR
VAR_OUTPUT
    Done    : BOOL;
    Busy    : BOOL;
    Error   : BOOL;
    ErrorID : DWORD;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_CamIn
VAR_IN_OUT
    Slave              : TO_SynchronousAxis;
END_VAR
VAR_INPUT
    Master             : REF_TO Motion.AXIS_REF_SM3;
    Execute            : BOOL;
    CamTableID         : Motion.MC_CAM_ID;
    StartMode          : Motion.MC_STARTMODE;
    MasterOffset       : LREAL;
    SlaveOffset        : LREAL;
    Velocity           : REAL;
    Acceleration       : REAL;
    Deceleration       : REAL;
    Jerk               : REAL;
    BufferMode         : Motion.MC_BUFFER_MODE;
END_VAR
VAR_OUTPUT
    InSync         : BOOL;
    Busy           : BOOL;
    CommandAborted : BOOL;
    Error          : BOOL;
    ErrorID        : DWORD;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_CamOut
VAR_IN_OUT
    Slave   : TO_SynchronousAxis;
END_VAR
VAR_INPUT
    Execute : BOOL;
END_VAR
VAR_OUTPUT
    Done    : BOOL;
    Busy    : BOOL;
    Error   : BOOL;
    ErrorID : DWORD;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_Phasing
VAR_IN_OUT
    Slave        : TO_SynchronousAxis;
END_VAR
VAR_INPUT
    Master       : REF_TO Motion.AXIS_REF_SM3;
    Execute      : BOOL;
    PhaseShift   : LREAL;
    Velocity     : REAL;
    Acceleration : REAL;
    Deceleration : REAL;
    Jerk         : REAL;
    BufferMode   : Motion.MC_BUFFER_MODE;
END_VAR
VAR_OUTPUT
    Done           : BOOL;
    Busy           : BOOL;
    CommandAborted : BOOL;
    Error          : BOOL;
    ErrorID        : DWORD;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_PositionProfile
VAR_IN_OUT
    Axis             : TO_SynchronousAxis;
END_VAR
VAR_INPUT
    Execute          : BOOL;
    TimePosition     : REF_TO Motion.MC_TP_REF;
    BufferMode       : Motion.MC_BUFFER_MODE;
END_VAR
VAR_OUTPUT
    Done           : BOOL;
    Busy           : BOOL;
    CommandAborted : BOOL;
    Error          : BOOL;
    ErrorID        : DWORD;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_VelocityProfile
VAR_IN_OUT
    Axis             : TO_SynchronousAxis;
END_VAR
VAR_INPUT
    Execute          : BOOL;
    TimeVelocity     : REF_TO Motion.MC_TV_REF;
    BufferMode       : Motion.MC_BUFFER_MODE;
END_VAR
VAR_OUTPUT
    Done           : BOOL;
    Busy           : BOOL;
    CommandAborted : BOOL;
    Error          : BOOL;
    ErrorID        : DWORD;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_AccelerationProfile
VAR_IN_OUT
    Axis                : TO_SynchronousAxis;
END_VAR
VAR_INPUT
    Execute             : BOOL;
    TimeAcceleration    : REF_TO Motion.MC_TA_REF;
    BufferMode          : Motion.MC_BUFFER_MODE;
END_VAR
VAR_OUTPUT
    Done           : BOOL;
    Busy           : BOOL;
    CommandAborted : BOOL;
    Error          : BOOL;
    ErrorID        : DWORD;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_ReadParameter
VAR_IN_OUT
    Axis            : TO_SynchronousAxis;
END_VAR
VAR_INPUT
    Enable          : BOOL;
    ParameterNumber : WORD;
END_VAR
VAR_OUTPUT
    Valid   : BOOL;
    Busy    : BOOL;
    Error   : BOOL;
    ErrorID : DWORD;
    Value   : LREAL;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_WriteParameter
VAR_IN_OUT
    Axis            : TO_SynchronousAxis;
END_VAR
VAR_INPUT
    Execute         : BOOL;
    ParameterNumber : WORD;
    Value           : LREAL;
END_VAR
VAR_OUTPUT
    Done    : BOOL;
    Busy    : BOOL;
    Error   : BOOL;
    ErrorID : DWORD;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_ReadBoolParameter
VAR_IN_OUT
    Axis            : TO_SynchronousAxis;
END_VAR
VAR_INPUT
    Enable          : BOOL;
    ParameterNumber : WORD;
END_VAR
VAR_OUTPUT
    Valid   : BOOL;
    Busy    : BOOL;
    Error   : BOOL;
    ErrorID : DWORD;
    Value   : BOOL;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_WriteBoolParameter
VAR_IN_OUT
    Axis            : TO_SynchronousAxis;
END_VAR
VAR_INPUT
    Execute         : BOOL;
    ParameterNumber : WORD;
    Value           : BOOL;
END_VAR
VAR_OUTPUT
    Done    : BOOL;
    Busy    : BOOL;
    Error   : BOOL;
    ErrorID : DWORD;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_TouchProbe
VAR_IN_OUT
    Axis             : TO_SynchronousAxis;
END_VAR
VAR_INPUT
    Execute          : BOOL;
    TriggerInput     : REF_TO Motion.TRIGGER_REF;
    WindowOnly       : BOOL;
    FirstPosition    : LREAL;
    LastPosition     : LREAL;
END_VAR
VAR_OUTPUT
    Done             : BOOL;
    Busy             : BOOL;
    CommandAborted   : BOOL;
    Error            : BOOL;
    ErrorID          : DWORD;
    RecordedPosition : LREAL;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_AbortTrigger
VAR_IN_OUT
    Axis         : TO_SynchronousAxis;
END_VAR
VAR_INPUT
    Execute      : BOOL;
    TriggerInput : REF_TO Motion.TRIGGER_REF;
END_VAR
VAR_OUTPUT
    Done    : BOOL;
    Busy    : BOOL;
    Error   : BOOL;
    ErrorID : DWORD;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_ReadActualPosition
VAR_IN_OUT
    Axis   : TO_SynchronousAxis;
END_VAR
VAR_INPUT
    Enable : BOOL;
END_VAR
VAR_OUTPUT
    Valid    : BOOL;
    Busy     : BOOL;
    Error    : BOOL;
    ErrorID  : DWORD;
    Position : LREAL;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_ReadActualVelocity
VAR_IN_OUT
    Axis   : TO_SynchronousAxis;
END_VAR
VAR_INPUT
    Enable : BOOL;
END_VAR
VAR_OUTPUT
    Valid    : BOOL;
    Busy     : BOOL;
    Error    : BOOL;
    ErrorID  : DWORD;
    Velocity : LREAL;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_ReadActualTorque
VAR_IN_OUT
    Axis   : TO_SynchronousAxis;
END_VAR
VAR_INPUT
    Enable : BOOL;
END_VAR
VAR_OUTPUT
    Valid   : BOOL;
    Busy    : BOOL;
    Error   : BOOL;
    ErrorID : DWORD;
    Torque  : LREAL;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_ReadAxisError
VAR_IN_OUT
    Axis   : TO_SynchronousAxis;
END_VAR
VAR_INPUT
    Enable : BOOL;
END_VAR
VAR_OUTPUT
    Valid       : BOOL;
    Busy        : BOOL;
    Error       : BOOL;
    ErrorID     : DWORD;
    AxisErrorID : DWORD;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_ReadStatus
VAR_IN_OUT
    Axis               : TO_SynchronousAxis;
END_VAR
VAR_INPUT
    Enable             : BOOL;
END_VAR
VAR_OUTPUT
    Valid              : BOOL;
    Busy               : BOOL;
    Error              : BOOL;
    ErrorID            : DWORD;
    ErrorStop          : BOOL;
    Disabled           : BOOL;
    Stopping           : BOOL;
    Homing             : BOOL;
    Standstill         : BOOL;
    DiscreteMotion     : BOOL;
    ContinuousMotion   : BOOL;
    SynchronizedMotion : BOOL;
END_VAR
END_FUNCTION_BLOCK

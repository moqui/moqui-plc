(* Compile-only compatibility stubs for Motion profile.
   Provides CoordMotion namespace types and group MC_ function-block shells
   that AxisGroup.st references.  No runtime logic here. *)

(* Kinematics group object reference, used as VAR_IN_OUT in AxisGroup.st *)
TYPE
    TO_Kinematics : STRUCT
        dummy : BOOL;
    END_STRUCT;
END_TYPE

NAMESPACE CoordMotion

    TYPE
        (* 6-DOF Cartesian position used for move target/actual *)
        SMC_POS_REF : STRUCT
            X : LREAL;
            Y : LREAL;
            Z : LREAL;
            A : LREAL;
            B : LREAL;
            C : LREAL;
        END_STRUCT;

        SMC_CIRC_MODE : USINT
            ( BORDER := USINT#0
            , CENTER := USINT#1 ) := USINT#0;

        MC_CIRC_PATHCHOICE : USINT
            ( CLOCKWISE        := USINT#0
            , COUNTERCLOCKWISE := USINT#1 ) := USINT#0;

        SMC_COORD_SYSTEM : USINT
            ( MCS := USINT#0
            , WCS := USINT#1
            , TCS := USINT#2
            , ACS := USINT#3 ) := USINT#0;

        MC_TRANSITION_MODE : USINT
            ( TMNone               := USINT#0
            , TMStartVelocity      := USINT#1
            , TMCornerDistance     := USINT#2
            , TMMaxCornerDeviation := USINT#3 ) := USINT#0;
    END_TYPE

END_NAMESPACE


FUNCTION_BLOCK MC_GroupEnable
VAR_IN_OUT
    AxisGroup : TO_Kinematics;
END_VAR
VAR_INPUT
    Execute   : BOOL;
END_VAR
VAR_OUTPUT
    Done    : BOOL;
    Busy    : BOOL;
    Error   : BOOL;
    ErrorID : DWORD;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_GroupReset
VAR_IN_OUT
    AxisGroup : TO_Kinematics;
END_VAR
VAR_INPUT
    Execute   : BOOL;
END_VAR
VAR_OUTPUT
    Done    : BOOL;
    Busy    : BOOL;
    Error   : BOOL;
    ErrorID : DWORD;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_GroupHalt
VAR_IN_OUT
    AxisGroup    : TO_Kinematics;
END_VAR
VAR_INPUT
    Execute      : BOOL;
    Deceleration : LREAL;
    Jerk         : LREAL;
    AccFactor    : REAL;
    JerkFactor   : REAL;
END_VAR
VAR_OUTPUT
    Done           : BOOL;
    Busy           : BOOL;
    CommandAborted : BOOL;
    Error          : BOOL;
    ErrorID        : DWORD;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_GroupStop
VAR_IN_OUT
    AxisGroup    : TO_Kinematics;
END_VAR
VAR_INPUT
    Execute      : BOOL;
    Deceleration : LREAL;
    Jerk         : LREAL;
END_VAR
VAR_OUTPUT
    Done    : BOOL;
    Busy    : BOOL;
    Error   : BOOL;
    ErrorID : DWORD;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_GroupReadStatus
VAR_IN_OUT
    AxisGroup      : TO_Kinematics;
END_VAR
VAR_INPUT
    Enable         : BOOL;
END_VAR
VAR_OUTPUT
    Valid          : BOOL;
    Busy           : BOOL;
    Error          : BOOL;
    ErrorID        : DWORD;
    GroupErrorStop : BOOL;
    GroupStopping  : BOOL;
    GroupMoving    : BOOL;
    GroupStandby   : BOOL;
    GroupHoming    : BOOL;
    GroupDisabled  : BOOL;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_GroupReadError
VAR_IN_OUT
    AxisGroup    : TO_Kinematics;
END_VAR
VAR_INPUT
    Enable       : BOOL;
END_VAR
VAR_OUTPUT
    Valid        : BOOL;
    Busy         : BOOL;
    Error        : BOOL;
    ErrorID      : DWORD;
    GroupErrorID : DWORD;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_GroupReadActualPosition
VAR_IN_OUT
    AxisGroup   : TO_Kinematics;
END_VAR
VAR_INPUT
    Enable      : BOOL;
    CoordSystem : CoordMotion.SMC_COORD_SYSTEM;
END_VAR
VAR_OUTPUT
    Valid    : BOOL;
    Busy     : BOOL;
    Error    : BOOL;
    ErrorID  : DWORD;
    Position : CoordMotion.SMC_POS_REF;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_GroupReadActualVelocity
VAR_IN_OUT
    AxisGroup   : TO_Kinematics;
END_VAR
VAR_INPUT
    Enable      : BOOL;
    CoordSystem : CoordMotion.SMC_COORD_SYSTEM;
END_VAR
VAR_OUTPUT
    Valid    : BOOL;
    Busy     : BOOL;
    Error    : BOOL;
    ErrorID  : DWORD;
    Velocity : CoordMotion.SMC_POS_REF;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_GroupSetOverride
VAR_IN_OUT
    AxisGroup  : TO_Kinematics;
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

FUNCTION_BLOCK MC_MoveLinearAbsolute
VAR_IN_OUT
    AxisGroup           : TO_Kinematics;
END_VAR
VAR_INPUT
    Execute             : BOOL;
    Position            : CoordMotion.SMC_POS_REF;
    Velocity            : LREAL;
    Acceleration        : LREAL;
    Deceleration        : LREAL;
    Jerk                : LREAL;
    CoordSystem         : CoordMotion.SMC_COORD_SYSTEM;
    BufferMode          : Motion.MC_BUFFER_MODE;
    TransitionMode      : CoordMotion.MC_TRANSITION_MODE;
    TransitionParameter : ARRAY [0..9] OF LREAL;
END_VAR
VAR_OUTPUT
    Done           : BOOL;
    Busy           : BOOL;
    CommandAborted : BOOL;
    Error          : BOOL;
    ErrorID        : DWORD;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_MoveLinearRelative
VAR_IN_OUT
    AxisGroup           : TO_Kinematics;
END_VAR
VAR_INPUT
    Execute             : BOOL;
    Distance            : CoordMotion.SMC_POS_REF;
    Velocity            : LREAL;
    Acceleration        : LREAL;
    Deceleration        : LREAL;
    Jerk                : LREAL;
    CoordSystem         : CoordMotion.SMC_COORD_SYSTEM;
    BufferMode          : Motion.MC_BUFFER_MODE;
    TransitionMode      : CoordMotion.MC_TRANSITION_MODE;
    TransitionParameter : ARRAY [0..9] OF LREAL;
END_VAR
VAR_OUTPUT
    Done           : BOOL;
    Busy           : BOOL;
    CommandAborted : BOOL;
    Error          : BOOL;
    ErrorID        : DWORD;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_MoveCircularAbsolute
VAR_IN_OUT
    AxisGroup           : TO_Kinematics;
END_VAR
VAR_INPUT
    Execute             : BOOL;
    CircMode            : CoordMotion.SMC_CIRC_MODE;
    AuxPoint            : CoordMotion.SMC_POS_REF;
    EndPoint            : CoordMotion.SMC_POS_REF;
    PathChoice          : CoordMotion.MC_CIRC_PATHCHOICE;
    Velocity            : LREAL;
    Acceleration        : LREAL;
    Deceleration        : LREAL;
    Jerk                : LREAL;
    CoordSystem         : CoordMotion.SMC_COORD_SYSTEM;
    BufferMode          : Motion.MC_BUFFER_MODE;
    TransitionMode      : CoordMotion.MC_TRANSITION_MODE;
    TransitionParameter : ARRAY [0..9] OF LREAL;
END_VAR
VAR_OUTPUT
    Done           : BOOL;
    Busy           : BOOL;
    CommandAborted : BOOL;
    Error          : BOOL;
    ErrorID        : DWORD;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_MoveCircularRelative
VAR_IN_OUT
    AxisGroup           : TO_Kinematics;
END_VAR
VAR_INPUT
    Execute             : BOOL;
    CircMode            : CoordMotion.SMC_CIRC_MODE;
    AuxPoint            : CoordMotion.SMC_POS_REF;
    EndPoint            : CoordMotion.SMC_POS_REF;
    PathChoice          : CoordMotion.MC_CIRC_PATHCHOICE;
    Velocity            : LREAL;
    Acceleration        : LREAL;
    Deceleration        : LREAL;
    Jerk                : LREAL;
    CoordSystem         : CoordMotion.SMC_COORD_SYSTEM;
    BufferMode          : Motion.MC_BUFFER_MODE;
    TransitionMode      : CoordMotion.MC_TRANSITION_MODE;
    TransitionParameter : ARRAY [0..9] OF LREAL;
END_VAR
VAR_OUTPUT
    Done           : BOOL;
    Busy           : BOOL;
    CommandAborted : BOOL;
    Error          : BOOL;
    ErrorID        : DWORD;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_MoveDirectAbsolute
VAR_IN_OUT
    AxisGroup           : TO_Kinematics;
END_VAR
VAR_INPUT
    Execute             : BOOL;
    Position            : CoordMotion.SMC_POS_REF;
    Velocity            : LREAL;
    Acceleration        : LREAL;
    Deceleration        : LREAL;
    Jerk                : LREAL;
    CoordSystem         : CoordMotion.SMC_COORD_SYSTEM;
    BufferMode          : Motion.MC_BUFFER_MODE;
    TransitionMode      : CoordMotion.MC_TRANSITION_MODE;
    TransitionParameter : ARRAY [0..9] OF LREAL;
END_VAR
VAR_OUTPUT
    Done           : BOOL;
    Busy           : BOOL;
    CommandAborted : BOOL;
    Error          : BOOL;
    ErrorID        : DWORD;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_MoveDirectRelative
VAR_IN_OUT
    AxisGroup           : TO_Kinematics;
END_VAR
VAR_INPUT
    Execute             : BOOL;
    Distance            : CoordMotion.SMC_POS_REF;
    Velocity            : LREAL;
    Acceleration        : LREAL;
    Deceleration        : LREAL;
    Jerk                : LREAL;
    CoordSystem         : CoordMotion.SMC_COORD_SYSTEM;
    BufferMode          : Motion.MC_BUFFER_MODE;
    TransitionMode      : CoordMotion.MC_TRANSITION_MODE;
    TransitionParameter : ARRAY [0..9] OF LREAL;
END_VAR
VAR_OUTPUT
    Done           : BOOL;
    Busy           : BOOL;
    CommandAborted : BOOL;
    Error          : BOOL;
    ErrorID        : DWORD;
END_VAR
END_FUNCTION_BLOCK

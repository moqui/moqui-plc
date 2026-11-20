(* PLCopen Motion Control Part 4 - axis group function blocks used by moqui-plc.
 *
 * Interface declarations only (no implementation), for type checking with a
 * non-CODESYS compiler. Parameters follow the PLCopen function block
 * interface; positions use SMC_POS_REF, the CODESYS position type
 * (codesys-softmotion/softmotion.st).
 * A runtime that hosts moqui-plc implements these blocks with the same
 * signatures.
 *)

FUNCTION_BLOCK MC_GroupEnable
VAR_IN_OUT
    AxisGroup : AXES_GROUP_REF;
END_VAR
VAR_INPUT
    Execute : BOOL;
END_VAR
VAR_OUTPUT
    Done : BOOL;
    Busy : BOOL;
    Error : BOOL;
    ErrorID : WORD;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_GroupDisable
VAR_IN_OUT
    AxisGroup : AXES_GROUP_REF;
END_VAR
VAR_INPUT
    Execute : BOOL;
END_VAR
VAR_OUTPUT
    Done : BOOL;
    Busy : BOOL;
    Error : BOOL;
    ErrorID : WORD;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_GroupReset
VAR_IN_OUT
    AxisGroup : AXES_GROUP_REF;
END_VAR
VAR_INPUT
    Execute : BOOL;
END_VAR
VAR_OUTPUT
    Done : BOOL;
    Busy : BOOL;
    Error : BOOL;
    ErrorID : WORD;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_GroupStop
VAR_IN_OUT
    AxisGroup : AXES_GROUP_REF;
END_VAR
VAR_INPUT
    Execute : BOOL;
    Deceleration : LREAL;
    Jerk : LREAL;
END_VAR
VAR_OUTPUT
    Done : BOOL;
    Busy : BOOL;
    CommandAborted : BOOL;
    Error : BOOL;
    ErrorID : WORD;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_GroupHalt
VAR_IN_OUT
    AxisGroup : AXES_GROUP_REF;
END_VAR
VAR_INPUT
    Execute : BOOL;
    Deceleration : LREAL;
    Jerk : LREAL;
    AccFactor : LREAL;
    JerkFactor : LREAL;
    BufferMode : MC_BUFFER_MODE;
END_VAR
VAR_OUTPUT
    Done : BOOL;
    Busy : BOOL;
    Active : BOOL;
    CommandAborted : BOOL;
    Error : BOOL;
    ErrorID : WORD;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_GroupSetOverride
VAR_IN_OUT
    AxisGroup : AXES_GROUP_REF;
END_VAR
VAR_INPUT
    Enable : BOOL;
    VelFactor : LREAL;
    AccFactor : LREAL;
    JerkFactor : LREAL;
END_VAR
VAR_OUTPUT
    Enabled : BOOL;
    Busy : BOOL;
    Error : BOOL;
    ErrorID : WORD;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_GroupReadActualPosition
VAR_IN_OUT
    AxisGroup : AXES_GROUP_REF;
END_VAR
VAR_INPUT
    Enable : BOOL;
    CoordSystem : SMC_COORD_SYSTEM;
END_VAR
VAR_OUTPUT
    Valid : BOOL;
    Busy : BOOL;
    Error : BOOL;
    ErrorID : WORD;
    Position : SMC_POS_REF;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_GroupReadActualVelocity
VAR_IN_OUT
    AxisGroup : AXES_GROUP_REF;
END_VAR
VAR_INPUT
    Enable : BOOL;
    CoordSystem : SMC_COORD_SYSTEM;
END_VAR
VAR_OUTPUT
    Valid : BOOL;
    Busy : BOOL;
    Error : BOOL;
    ErrorID : WORD;
    Velocity : SMC_POS_REF;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_GroupReadError
VAR_IN_OUT
    AxisGroup : AXES_GROUP_REF;
END_VAR
VAR_INPUT
    Enable : BOOL;
END_VAR
VAR_OUTPUT
    Valid : BOOL;
    Busy : BOOL;
    Error : BOOL;
    ErrorID : WORD;
    GroupErrorID : DWORD;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_GroupReadStatus
VAR_IN_OUT
    AxisGroup : AXES_GROUP_REF;
END_VAR
VAR_INPUT
    Enable : BOOL;
END_VAR
VAR_OUTPUT
    Valid : BOOL;
    Busy : BOOL;
    Error : BOOL;
    ErrorID : WORD;
    GroupMoving : BOOL;
    GroupHoming : BOOL;
    GroupErrorStop : BOOL;
    GroupStandby : BOOL;
    GroupStopping : BOOL;
    GroupDisabled : BOOL;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_MoveLinearAbsolute
VAR_IN_OUT
    AxisGroup : AXES_GROUP_REF;
END_VAR
VAR_INPUT
    Execute : BOOL;
    Position : SMC_POS_REF;
    Velocity : LREAL;
    Acceleration : LREAL;
    Deceleration : LREAL;
    Jerk : LREAL;
    CoordSystem : SMC_COORD_SYSTEM;
    BufferMode : MC_BUFFER_MODE;
    TransitionMode : MC_TRANSITION_MODE;
    TransitionParameter : ARRAY [0..(SMC_RCNST.MAX_TRANS_PARAMS - 1)] OF LREAL;
END_VAR
VAR_OUTPUT
    Done : BOOL;
    Busy : BOOL;
    Active : BOOL;
    CommandAborted : BOOL;
    Error : BOOL;
    ErrorID : WORD;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_MoveLinearRelative
VAR_IN_OUT
    AxisGroup : AXES_GROUP_REF;
END_VAR
VAR_INPUT
    Execute : BOOL;
    Distance : SMC_POS_REF;
    Velocity : LREAL;
    Acceleration : LREAL;
    Deceleration : LREAL;
    Jerk : LREAL;
    CoordSystem : SMC_COORD_SYSTEM;
    BufferMode : MC_BUFFER_MODE;
    TransitionMode : MC_TRANSITION_MODE;
    TransitionParameter : ARRAY [0..(SMC_RCNST.MAX_TRANS_PARAMS - 1)] OF LREAL;
END_VAR
VAR_OUTPUT
    Done : BOOL;
    Busy : BOOL;
    Active : BOOL;
    CommandAborted : BOOL;
    Error : BOOL;
    ErrorID : WORD;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_MoveDirectAbsolute
VAR_IN_OUT
    AxisGroup : AXES_GROUP_REF;
END_VAR
VAR_INPUT
    Execute : BOOL;
    Position : SMC_POS_REF;
    CoordSystem : SMC_COORD_SYSTEM;
    BufferMode : MC_BUFFER_MODE;
    TransitionMode : MC_TRANSITION_MODE;
    TransitionParameter : ARRAY [0..(SMC_RCNST.MAX_TRANS_PARAMS - 1)] OF LREAL;
END_VAR
VAR_OUTPUT
    Done : BOOL;
    Busy : BOOL;
    Active : BOOL;
    CommandAborted : BOOL;
    Error : BOOL;
    ErrorID : WORD;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_MoveDirectRelative
VAR_IN_OUT
    AxisGroup : AXES_GROUP_REF;
END_VAR
VAR_INPUT
    Execute : BOOL;
    Distance : SMC_POS_REF;
    CoordSystem : SMC_COORD_SYSTEM;
    BufferMode : MC_BUFFER_MODE;
    TransitionMode : MC_TRANSITION_MODE;
    TransitionParameter : ARRAY [0..(SMC_RCNST.MAX_TRANS_PARAMS - 1)] OF LREAL;
END_VAR
VAR_OUTPUT
    Done : BOOL;
    Busy : BOOL;
    Active : BOOL;
    CommandAborted : BOOL;
    Error : BOOL;
    ErrorID : WORD;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_MoveCircularAbsolute
VAR_IN_OUT
    AxisGroup : AXES_GROUP_REF;
END_VAR
VAR_INPUT
    Execute : BOOL;
    CircMode : SMC_CIRC_MODE;
    AuxPoint : SMC_POS_REF;
    EndPoint : SMC_POS_REF;
    PathChoice : MC_CIRC_PATHCHOICE;
    Velocity : LREAL;
    Acceleration : LREAL;
    Deceleration : LREAL;
    Jerk : LREAL;
    CoordSystem : SMC_COORD_SYSTEM;
    BufferMode : MC_BUFFER_MODE;
    TransitionMode : MC_TRANSITION_MODE;
    TransitionParameter : ARRAY [0..(SMC_RCNST.MAX_TRANS_PARAMS - 1)] OF LREAL;
END_VAR
VAR_OUTPUT
    Done : BOOL;
    Busy : BOOL;
    Active : BOOL;
    CommandAborted : BOOL;
    Error : BOOL;
    ErrorID : WORD;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_MoveCircularRelative
VAR_IN_OUT
    AxisGroup : AXES_GROUP_REF;
END_VAR
VAR_INPUT
    Execute : BOOL;
    CircMode : SMC_CIRC_MODE;
    AuxPoint : SMC_POS_REF;
    EndPoint : SMC_POS_REF;
    PathChoice : MC_CIRC_PATHCHOICE;
    Velocity : LREAL;
    Acceleration : LREAL;
    Deceleration : LREAL;
    Jerk : LREAL;
    CoordSystem : SMC_COORD_SYSTEM;
    BufferMode : MC_BUFFER_MODE;
    TransitionMode : MC_TRANSITION_MODE;
    TransitionParameter : ARRAY [0..(SMC_RCNST.MAX_TRANS_PARAMS - 1)] OF LREAL;
END_VAR
VAR_OUTPUT
    Done : BOOL;
    Busy : BOOL;
    Active : BOOL;
    CommandAborted : BOOL;
    Error : BOOL;
    ErrorID : WORD;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_SetCoordinateTransform
VAR_IN_OUT
    AxisGroup : AXES_GROUP_REF;
END_VAR
VAR_INPUT
    Execute : BOOL;
    CoordSystem : SMC_COORD_SYSTEM;
    CoordTransform : MC_COORD_REF;
    BufferMode : MC_BUFFER_MODE;
END_VAR
VAR_OUTPUT
    Done : BOOL;
    Busy : BOOL;
    Error : BOOL;
    ErrorID : WORD;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_TrackConveyorBelt
VAR_IN_OUT
    AxisGroup : AXES_GROUP_REF;
    ConveyorBelt : AXIS_REF;
END_VAR
VAR_INPUT
    Execute : BOOL;
    ConveyorBeltOrigin : MC_COORD_REF;
    InitialObjectPosition : MC_COORD_REF;
    CoordSystem : SMC_COORD_SYSTEM;
END_VAR
VAR_OUTPUT
    Done : BOOL;
    Busy : BOOL;
    Error : BOOL;
    ErrorID : WORD;
    cs : SMC_CoordinateSystem;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK MC_TrackRotaryTable
VAR_IN_OUT
    AxisGroup : AXES_GROUP_REF;
    RotaryTable : AXIS_REF;
END_VAR
VAR_INPUT
    Execute : BOOL;
    RotaryTableOrigin : MC_COORD_REF;
    InitialObjectPosition : MC_COORD_REF;
    CoordSystem : SMC_COORD_SYSTEM;
END_VAR
VAR_OUTPUT
    Done : BOOL;
    Busy : BOOL;
    Error : BOOL;
    ErrorID : WORD;
    cs : SMC_CoordinateSystem;
END_VAR
END_FUNCTION_BLOCK

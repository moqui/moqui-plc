(*
 * AxisGroup: coordinated multi-axis motion over a kinematics group.
 *
 * FSM structure:
 *   Start-up : NotPowered -> Enabling -> Standby
 *              (axes must be powered by the caller via MC_Power before groupEnable is set)
 *   Motion   : Standby -> [MoveLinearAbsolute | MoveLinearRelative |
 *                         MoveCircularAbsolute | MoveCircularRelative |
 *                         MoveDirectAbsolute | MoveDirectRelative |
 *                         HaltState | StoppingState] -> Standby
 *   Error    : Any state -> Error --(reset rising edge)--> WaitReset
 *              WaitReset --(MC_GroupReset.Done)--> Standby  (axes remain powered)
 *
 * Caller responsibility:
 *   Power individual axes with MC_Power (one instance per axis) before setting groupEnable.
 *   SMC_GroupPower is NOT used here - it requires the same task as the axis group,
 *   which is not always the case.
 *
 * CODESYS-specific additions (minimum necessary):
 *   AXIS_GROUP_REF_SM3 - CODESYS group reference type
 *   SMC_POS_REF - CODESYS 6-DOF position type (X,Y,Z,A,B,C : LREAL)
 *   c_maxTransitionParameter - CODESYS constant for transition parameter array size
 *
 * Caller pattern:
 *   grp.cmd := AxisGroupCmd.MoveLinearAbsolute;
 *   grp.endPoint := targetPos;    SMC_POS_REF
 *   grp.velocity := 500.0;
 *   grp(group := groupRef, groupEnable := enableFlag);
 *   done := grp.commandExecuted;
 *
 * MC_MoveDirectAbsolute / MC_MoveDirectRelative take no velocity / acceleration /
 * deceleration / jerk inputs - dynamics are defined per-axis in drive parameters.
 *
 * MC_GroupStop is level-driven (Execute must remain TRUE while stopping) and
 * is NOT abortable by another motion command; MC_GroupHalt is abortable.
 *
 * Error recovery via MC_GroupReset returns directly to Standby (GroupStandby state):
 * axes remain powered; no re-homing required.
 *
 * AX_TODO: SIMATIC AX manual override.
 * AXIS_GROUP_REF_SM3 -> TO_Kinematics (Siemens kinematics group type for SIMATIC AX).
 * SMC_POS_REF -> AX_PositionStruct (6-DOF struct: X,Y,Z,A,B,C : LREAL; verify AX library type name).
 * CoordMotion namespace -> MC_ / Siemens kinematics library FBs (verify AX library names).
 * SMC_RCNST.MAX_TRANS_PARAMS -> use fixed array size or AX constant equivalent.
 * MC_BUFFER_MODE / enum access: Dot notation -> Hash notation (applied).
 * AxisGroupCmd / AxisGroupInternalStatus / AxisGroupStatus enum access: applied.
 * Circular motion: CircMode, PathChoice parameter names; verify AX library signature.
 * readGroupActPos / readGroupActVel: verify Position/Velocity output field names in AX library.
 * groupSetOverride AccFactor/JerkFactor: verify AX library signature.
 * haltGroup AccFactor/JerkFactor: verify AX library signature.
 *)
FUNCTION_BLOCK AxisGroup
VAR_INPUT
	(* Axis group metadata for logging purpose *)
	axisGroupId : STRING;
	axisGroupName : STRING;

    (* Motion command *)
    cmd : AxisGroupCmd := AxisGroupCmd#Idle;

    (* Target position - absolute or relative endpoint (MCS / ACS / PCS per coordinateSystem) *)
    endPoint : CoordMotion.SMC_POS_REF;

    (* Auxiliary point for circular arc: via-point on arc (mcBorder) or arc centre (mcCenter) *)
    auxPoint : CoordMotion.SMC_POS_REF;

    (* Circular arc definition *)
    circMode : CoordMotion.SMC_CIRC_MODE := CoordMotion.SMC_CIRC_MODE#BORDER;
    pathChoice : CoordMotion.MC_CIRC_PATHCHOICE := CoordMotion.MC_CIRC_PATHCHOICE#CLOCKWISE;

    (* Dynamics - NOT used by MoveDirectAbsolute / MoveDirectRelative *)
    velocity : LREAL; (* [u/s] *)
    acceleration : LREAL; (* [u/s²] *)
    deceleration : LREAL; (* [u/s³] *)
    jerk : LREAL; (* [u/s³] *)

    (* PLCopen coordinate system and buffer / transition parameters *)
    coordinateSystem : CoordMotion.SMC_COORD_SYSTEM := CoordMotion.SMC_COORD_SYSTEM#MCS;
    bufferMode : Motion.MC_BUFFER_MODE := Motion.MC_BUFFER_MODE#aborting;
    transitionMode : CoordMotion.MC_TRANSITION_MODE  := CoordMotion.MC_TRANSITION_MODE#TMNone;
    transitionParameter : LREAL := 0.0; (* single scalar: corner distance / max deviation / const velocity *)

    (* Override (always active when enabled) *)
    overrideEnable : BOOL;
    velFactor : REAL := REAL#1.0;
    accFactor : REAL := REAL#1.0;
    jerkFactor : REAL := REAL#1.0;

    (* Error reset - rising edge triggers MC_GroupReset + recovery to Standby *)
    reset : BOOL;
END_VAR
VAR_IN_OUT
    group : TO_Kinematics;
    groupEnable : BOOL; (* TRUE = run group; FALSE = power down -> NotPowered *)
END_VAR
VAR_OUTPUT
    ready : BOOL; (* TRUE while in Standby, accepting commands *)
    commandExecuted : BOOL;(* Current command reached steady-state *)
    commandAborted : BOOL; (* Current command was aborted by a command change *)
    groupError : BOOL; (* Group in Error state - inspect groupErrorId *)
    groupErrorId : DWORD; (* Error code from MC_GroupReadError *)
    groupNotInitialized : BOOL; (* TRUE while NotPowered / WaitPower / Enabling *)
    status : AxisGroupStatus;
    actualPosition : CoordMotion.SMC_POS_REF; (* MCS TCP position, updated every cycle *)
    actualVelocity : CoordMotion.SMC_POS_REF; (* TCP velocity, updated every cycle *)
    cmdError : BOOL; (* TRUE = a motion FB triggered the Error state *)
    cmdErrorId : DWORD; (* Error code captured at moment cmdError was set *)
	(* Logger name for centralized signal management *)
	loggerName : STRING;
END_VAR
VAR
    (* FSM state *)
    internalStatus : AxisGroupInternalStatus := AxisGroupInternalStatus#NotPowered;

    (* Change-detection shadow variables *)
    oldCmd : AxisGroupCmd;
    oldEndPoint : CoordMotion.SMC_POS_REF;
    oldAuxPoint : CoordMotion.SMC_POS_REF;
    oldVelocity : LREAL;

    (* One-level pending command slot - PLCopen BufferMode *)
    hasPending : BOOL;
    pendingCmd : AxisGroupCmd;
    pendingEndPoint : CoordMotion.SMC_POS_REF;
    pendingAuxPoint : CoordMotion.SMC_POS_REF;
    pendingVelocity : LREAL;

    (* Reset edge detection *)
    resetOld : BOOL;
    resetActivation : BOOL;

    (*
     * Execute / enable signals driven exclusively by the FSM.
     * Consumed by the unconditional PLCopen FB calls at the bottom.
     *)
    groupEnableExecute : BOOL;
    groupResetExecute : BOOL;
    moveLinearAbsoluteExecute : BOOL;
    moveLinearRelativeExecute : BOOL;
    moveCircularAbsoluteExecute : BOOL;
    moveCircularRelativeExecute : BOOL;
    moveDirectAbsoluteExecute : BOOL;
    moveDirectRelativeExecute : BOOL;
    groupHaltExecute : BOOL;
    groupStopExecute : BOOL;

    (*
     * PLCopen + CODESYS group FBs - declared as VAR, called unconditionally every cycle.
     * Prefix mc_ / smc_ distinguishes FB instances from their homonymous VAR_IN_OUT.
     *)

    (* PLCopen Part 4 group management *)
    enableGroup : MC_GroupEnable;
    resetGroup : MC_GroupReset;
    readGroupStatus : MC_GroupReadStatus;
    readGroupError : MC_GroupReadError;
    readGroupActPos : MC_GroupReadActualPosition;
    readGroupActVel : MC_GroupReadActualVelocity;
    groupSetOverride : MC_GroupSetOverride;

    (* PLCopen Part 4 motion FBs *)
    moveLinearAbsolute : MC_MoveLinearAbsolute;
    moveLinearRelative : MC_MoveLinearRelative;
    moveCircularAbsolute : MC_MoveCircularAbsolute;
    moveCircularRelative : MC_MoveCircularRelative;
    moveDirectAbsolute : MC_MoveDirectAbsolute;
    moveDirectRelative : MC_MoveDirectRelative;
    haltGroup : MC_GroupHalt;
    stopGroup : MC_GroupStop;

    (* Transition parameter array - PLCopen Part 4 uses ARRAY[1..N] OF LREAL.
       Scalar input transitionParameter is mapped to index [1] each cycle. *)
    transParamArr : ARRAY [0..9] OF LREAL;
	(* Logger facade *)
	logger : LoggerFacade;
	init : BOOL;
END_VAR

IF NOT init THEN
	(* Args validation *)
	IF (axisGroupId = '' AND axisGroupName = '') THEN
		groupNotInitialized := TRUE;
		RETURN;
	END_IF;

	(* Logger facade init *)
	loggerName := System.Strings.Concat(axisGroupName, '[', axisGroupId, ']');
	logger.enable := TRUE; logger.loggerName := loggerName;
	init := TRUE;
END_IF;

logger(message := 'Running axis group.', level := LogLevel#DEBUG);

(* Reset edge detection *)
resetActivation := reset AND NOT resetOld;
resetOld := reset;

(* Map scalar transitionParameter -> array index [0] each cycle (0-based: ARRAY[0..MAX_TRANS_PARAMS-1]) *)
transParamArr[0] := transitionParameter;

(*
 * Error Detection - executed first, every PLC cycle.
 * Any motion FB reporting Error, or the group entering ErrorStop independently
 * (hardware fault, limit switch, etc.), routes the FSM to Error state.
 * mc_GroupReadError.Error is the diagnostic FB's own fault - intentionally excluded.
 *)
IF internalStatus <> AxisGroupInternalStatus#Error AND
        internalStatus <> AxisGroupInternalStatus#WaitReset THEN
    IF enableGroup.Error OR resetGroup.Error OR
            moveLinearAbsolute.Error OR moveLinearRelative.Error OR
       		moveCircularAbsolute.Error OR moveCircularRelative.Error OR
       		moveDirectAbsolute.Error OR moveDirectRelative.Error OR
       		haltGroup.Error OR stopGroup.Error THEN
        internalStatus := AxisGroupInternalStatus#Error;
        commandAborted := TRUE;
        cmdError := TRUE;
        cmdErrorId := readGroupError.GroupErrorID;
		logger(message := 'Axis group error.', level := LogLevel#DEBUG);
    ELSIF readGroupStatus.GroupErrorStop AND
          TO_UINT(internalStatus) >= TO_UINT(AxisGroupInternalStatus#Standby) THEN
        (* Ignore GroupErrorStop during init - startup from ErrorStop is handled in WaitPower *)
        internalStatus := AxisGroupInternalStatus#Error;
        commandAborted := TRUE;
        cmdError := FALSE;
        cmdErrorId := DWORD#0;
    END_IF;
END_IF;

(* Error state: assert outputs and wait for reset rising edge. *)
IF internalStatus = AxisGroupInternalStatus#Error THEN
    groupError := TRUE;
    ready := FALSE;
    groupNotInitialized := TRUE;
    commandExecuted := FALSE;
    hasPending := FALSE;

    IF resetActivation THEN
        groupResetExecute := TRUE;
        internalStatus := AxisGroupInternalStatus#WaitReset;
    END_IF;

(*
 * WaitReset: MC_GroupReset transitions GroupErrorStop -> GroupStandby.
 * Axes remain powered; recovery goes directly to Standby (no re-homing).
 *)
ELSIF internalStatus = AxisGroupInternalStatus#WaitReset THEN
    IF resetGroup.Done THEN
        groupResetExecute := FALSE;
        moveLinearAbsoluteExecute := FALSE;
        moveLinearRelativeExecute := FALSE;
        moveCircularAbsoluteExecute := FALSE;
        moveCircularRelativeExecute := FALSE;
        moveDirectAbsoluteExecute := FALSE;
        moveDirectRelativeExecute := FALSE;
        groupHaltExecute := FALSE;
        groupStopExecute := FALSE;
        groupEnableExecute := FALSE;

        groupError := FALSE;
        groupErrorId := DWORD#0;
        cmdError := FALSE;
        cmdErrorId := DWORD#0;
        commandAborted := FALSE;
        commandExecuted := FALSE;

        oldCmd := AxisGroupCmd#Idle;
        hasPending := FALSE;
		logger(message := 'Axis group reset.', level := LogLevel#DEBUG);

        (* Axes remain powered - group is already in GroupStandby after MC_GroupReset *)
        internalStatus := AxisGroupInternalStatus#Standby;
    END_IF;
END_IF;

IF internalStatus = AxisGroupInternalStatus#Error OR
   internalStatus = AxisGroupInternalStatus#WaitReset THEN
    ; (* Fall through to unconditional FB calls below *)
ELSE

    (*
     * Power-off cross-cutting check - runs before the main FSM.
     * When groupEnable is withdrawn while the FSM is in any active state,
     * immediately clear all execute signals and power down.
     *)
    IF NOT groupEnable AND TO_UINT(internalStatus) >= TO_UINT(AxisGroupInternalStatus#Standby) THEN
        groupEnableExecute := FALSE;
        moveLinearAbsoluteExecute := FALSE;
        moveLinearRelativeExecute := FALSE;
        moveCircularAbsoluteExecute := FALSE;
        moveCircularRelativeExecute := FALSE;
        moveDirectAbsoluteExecute := FALSE;
        moveDirectRelativeExecute := FALSE;
        groupHaltExecute := FALSE;
        groupStopExecute := FALSE;
        groupResetExecute := FALSE;
        hasPending := FALSE;
        commandAborted := (internalStatus <> AxisGroupInternalStatus#Standby);
        internalStatus := AxisGroupInternalStatus#NotPowered;
    END_IF;

    (*
     * GroupStop cross-cutting check - runs before the main FSM.
     * MC_GroupStop is level-driven and supersedes any active motion.
     * Unlike MC_GroupHalt, it is NOT abortable by another motion command.
     *)
    IF cmd = AxisGroupCmd#GroupStop AND
       internalStatus <> AxisGroupInternalStatus#StoppingState AND
       TO_UINT(internalStatus) >= TO_UINT(AxisGroupInternalStatus#Standby) THEN

        moveLinearAbsoluteExecute := FALSE;
        moveLinearRelativeExecute := FALSE;
        moveCircularAbsoluteExecute := FALSE;
        moveCircularRelativeExecute := FALSE;
        moveDirectAbsoluteExecute := FALSE;
        moveDirectRelativeExecute := FALSE;
        groupHaltExecute := FALSE;
        groupStopExecute := TRUE;
        commandAborted := (internalStatus <> AxisGroupInternalStatus#Standby);
        oldCmd := cmd;
        internalStatus := AxisGroupInternalStatus#StoppingState;
    END_IF;

    (* Main FSM *)
    CASE internalStatus OF

        (* Initialization: clear all execute flags every cycle while unpowered. *)
        AxisGroupInternalStatus#NotPowered :
            moveLinearAbsoluteExecute := FALSE;
            moveLinearRelativeExecute := FALSE;
            moveCircularAbsoluteExecute := FALSE;
            moveCircularRelativeExecute := FALSE;
            moveDirectAbsoluteExecute := FALSE;
            moveDirectRelativeExecute := FALSE;
            groupHaltExecute := FALSE;
            groupStopExecute := FALSE;
            groupEnableExecute := FALSE;
            groupResetExecute := FALSE;
            hasPending := FALSE;

            groupNotInitialized := TRUE;
            ready := FALSE;

            IF groupEnable THEN
                groupEnableExecute := TRUE;
                internalStatus := AxisGroupInternalStatus#Enabling;
            END_IF;

        AxisGroupInternalStatus#Enabling :
			logger(message := 'Axis group enabling.', level := LogLevel#DEBUG);
            groupNotInitialized := TRUE;
            IF enableGroup.Done THEN
                groupEnableExecute := FALSE;
                internalStatus := AxisGroupInternalStatus#Standby;
            END_IF;

        (* Command dispatch - mirrors Axis.pou Ready state. *)
        AxisGroupInternalStatus#Standby :
            logger(message := 'Axis group ready to accept commands.', level := LogLevel#DEBUG);
			groupNotInitialized := FALSE;
            ready := TRUE;
            commandExecuted := FALSE;
            commandAborted := FALSE;

            IF NOT groupEnable THEN
                internalStatus := AxisGroupInternalStatus#NotPowered;

            ELSIF cmd = AxisGroupCmd#MoveLinearAbsolute THEN
                moveLinearAbsoluteExecute := TRUE;
                oldEndPoint := endPoint;
                oldVelocity := velocity;
                oldCmd := cmd;
                ready := FALSE;
                internalStatus := AxisGroupInternalStatus#MoveLinearAbsoluteState;

            ELSIF cmd = AxisGroupCmd#MoveLinearRelative THEN
                moveLinearRelativeExecute := TRUE;
                oldEndPoint := endPoint;
                oldVelocity := velocity;
                oldCmd := cmd;
                ready := FALSE;
                internalStatus := AxisGroupInternalStatus#MoveLinearRelativeState;

            ELSIF cmd = AxisGroupCmd#MoveCircularAbsolute THEN
                moveCircularAbsoluteExecute := TRUE;
                oldEndPoint := endPoint;
                oldAuxPoint := auxPoint;
                oldVelocity := velocity;
                oldCmd := cmd;
                ready := FALSE;
                internalStatus := AxisGroupInternalStatus#MoveCircularAbsoluteState;

            ELSIF cmd = AxisGroupCmd#MoveCircularRelative THEN
                moveCircularRelativeExecute := TRUE;
                oldEndPoint := endPoint;
                oldAuxPoint := auxPoint;
                oldVelocity := velocity;
                oldCmd := cmd;
                ready := FALSE;
                internalStatus := AxisGroupInternalStatus#MoveCircularRelativeState;

            ELSIF cmd = AxisGroupCmd#MoveDirectAbsolute THEN
                moveDirectAbsoluteExecute := TRUE;
                oldEndPoint := endPoint;
                oldCmd := cmd;
                ready := FALSE;
                internalStatus := AxisGroupInternalStatus#MoveDirectAbsoluteState;

            ELSIF cmd = AxisGroupCmd#MoveDirectRelative THEN
                moveDirectRelativeExecute := TRUE;
                oldEndPoint := endPoint;
                oldCmd := cmd;
                ready := FALSE;
                internalStatus := AxisGroupInternalStatus#MoveDirectRelativeState;

            ELSIF cmd = AxisGroupCmd#GroupHalt THEN
                groupHaltExecute := TRUE;
                oldCmd := cmd;
                ready := FALSE;
                internalStatus := AxisGroupInternalStatus#HaltState;

            END_IF;

        (* MoveLinearAbsolute *)
        AxisGroupInternalStatus#MoveLinearAbsoluteState :

            IF moveLinearAbsolute.Done THEN
                moveLinearAbsoluteExecute := FALSE;

                IF hasPending THEN
                    hasPending := FALSE;
                    oldCmd := pendingCmd;
                    oldEndPoint := pendingEndPoint;
                    oldAuxPoint := pendingAuxPoint;
                    oldVelocity := pendingVelocity;
                    commandExecuted := FALSE;
                    commandAborted := FALSE;

                    CASE oldCmd OF
                        AxisGroupCmd#MoveLinearAbsolute : moveLinearAbsoluteExecute := TRUE; internalStatus := AxisGroupInternalStatus#MoveLinearAbsoluteState;
                        AxisGroupCmd#MoveLinearRelative : moveLinearRelativeExecute := TRUE; internalStatus := AxisGroupInternalStatus#MoveLinearRelativeState;
                        AxisGroupCmd#MoveCircularAbsolute : moveCircularAbsoluteExecute := TRUE; internalStatus := AxisGroupInternalStatus#MoveCircularAbsoluteState;
                        AxisGroupCmd#MoveCircularRelative : moveCircularRelativeExecute := TRUE; internalStatus := AxisGroupInternalStatus#MoveCircularRelativeState;
                        AxisGroupCmd#MoveDirectAbsolute : moveDirectAbsoluteExecute := TRUE; internalStatus := AxisGroupInternalStatus#MoveDirectAbsoluteState;
                        AxisGroupCmd#MoveDirectRelative : moveDirectRelativeExecute := TRUE; internalStatus := AxisGroupInternalStatus#MoveDirectRelativeState;
                        AxisGroupCmd#GroupHalt : groupHaltExecute := TRUE; internalStatus := AxisGroupInternalStatus#HaltState;
                    ELSE
                        internalStatus := AxisGroupInternalStatus#Standby;
                    END_CASE;
                ELSE
                    commandExecuted := TRUE;
                    internalStatus := AxisGroupInternalStatus#CheckLinearAbsoluteState;
                END_IF;
            END_IF;

            IF cmd <> oldCmd THEN
                IF bufferMode = Motion.MC_BUFFER_MODE#aborting OR hasPending THEN
                    moveLinearAbsoluteExecute := FALSE;
                    IF hasPending THEN
                        CASE pendingCmd OF
                            AxisGroupCmd#MoveLinearAbsolute : moveLinearAbsoluteExecute := FALSE;
                            AxisGroupCmd#MoveLinearRelative : moveLinearRelativeExecute := FALSE;
                            AxisGroupCmd#MoveCircularAbsolute : moveCircularAbsoluteExecute := FALSE;
                            AxisGroupCmd#MoveCircularRelative : moveCircularRelativeExecute := FALSE;
                            AxisGroupCmd#MoveDirectAbsolute : moveDirectAbsoluteExecute := FALSE;
                            AxisGroupCmd#MoveDirectRelative : moveDirectRelativeExecute := FALSE;
                            AxisGroupCmd#GroupHalt : groupHaltExecute := FALSE;
                        END_CASE;

                        hasPending := FALSE;
                    END_IF;

                    commandAborted := TRUE;
                    internalStatus := AxisGroupInternalStatus#Standby;
                ELSE
                    pendingCmd := cmd;
                    pendingEndPoint := endPoint;
                    pendingAuxPoint := auxPoint;
                    pendingVelocity := velocity;
                    hasPending := TRUE;
                    oldCmd := pendingCmd;

                    CASE pendingCmd OF
                        AxisGroupCmd#MoveLinearAbsolute : moveLinearAbsoluteExecute := TRUE;
                        AxisGroupCmd#MoveLinearRelative : moveLinearRelativeExecute := TRUE;
                        AxisGroupCmd#MoveCircularAbsolute : moveCircularAbsoluteExecute := TRUE;
                        AxisGroupCmd#MoveCircularRelative : moveCircularRelativeExecute := TRUE;
                        AxisGroupCmd#MoveDirectAbsolute : moveDirectAbsoluteExecute := TRUE;
                        AxisGroupCmd#MoveDirectRelative : moveDirectRelativeExecute := TRUE;
                        AxisGroupCmd#GroupHalt : groupHaltExecute := TRUE;
                    ELSE
                        hasPending := FALSE;
                        commandAborted := TRUE;
                        internalStatus := AxisGroupInternalStatus#Standby;
                    END_CASE;
                END_IF;
            END_IF;

        AxisGroupInternalStatus#CheckLinearAbsoluteState :
            (* SMC_POS_REF fields cannot be compared directly - re-trigger is caller-driven via cmd change *)
            IF cmd <> oldCmd THEN
                commandExecuted := FALSE;
                internalStatus := AxisGroupInternalStatus#Standby;
            END_IF;

        (* MoveLinearRelative *)
        AxisGroupInternalStatus#MoveLinearRelativeState :

            IF moveLinearRelative.Done THEN
                moveLinearRelativeExecute := FALSE;
                IF hasPending THEN
                    hasPending := FALSE;
                    oldCmd := pendingCmd;
                    oldEndPoint := pendingEndPoint;
                    oldAuxPoint := pendingAuxPoint;
                    oldVelocity := pendingVelocity;
                    commandExecuted := FALSE;
                    commandAborted := FALSE;

                    CASE oldCmd OF
                        AxisGroupCmd#MoveLinearAbsolute : moveLinearAbsoluteExecute := TRUE; internalStatus := AxisGroupInternalStatus#MoveLinearAbsoluteState;
                        AxisGroupCmd#MoveLinearRelative : moveLinearRelativeExecute := TRUE; internalStatus := AxisGroupInternalStatus#MoveLinearRelativeState;
                        AxisGroupCmd#MoveCircularAbsolute : moveCircularAbsoluteExecute := TRUE; internalStatus := AxisGroupInternalStatus#MoveCircularAbsoluteState;
                        AxisGroupCmd#MoveCircularRelative : moveCircularRelativeExecute := TRUE; internalStatus := AxisGroupInternalStatus#MoveCircularRelativeState;
                        AxisGroupCmd#MoveDirectAbsolute : moveDirectAbsoluteExecute := TRUE; internalStatus := AxisGroupInternalStatus#MoveDirectAbsoluteState;
                        AxisGroupCmd#MoveDirectRelative : moveDirectRelativeExecute := TRUE; internalStatus := AxisGroupInternalStatus#MoveDirectRelativeState;
                        AxisGroupCmd#GroupHalt : groupHaltExecute := TRUE; internalStatus := AxisGroupInternalStatus#HaltState;
                    ELSE
                        internalStatus := AxisGroupInternalStatus#Standby;
                    END_CASE;
                ELSE
                    commandExecuted := TRUE;
                    internalStatus := AxisGroupInternalStatus#CheckLinearRelativeState;
                END_IF;
            END_IF;

            IF cmd <> oldCmd THEN
                IF bufferMode = Motion.MC_BUFFER_MODE#aborting OR hasPending THEN
                    moveLinearRelativeExecute := FALSE;
                    IF hasPending THEN
                        CASE pendingCmd OF
                            AxisGroupCmd#MoveLinearAbsolute : moveLinearAbsoluteExecute := FALSE;
                            AxisGroupCmd#MoveLinearRelative : moveLinearRelativeExecute := FALSE;
                            AxisGroupCmd#MoveCircularAbsolute : moveCircularAbsoluteExecute := FALSE;
                            AxisGroupCmd#MoveCircularRelative : moveCircularRelativeExecute := FALSE;
                            AxisGroupCmd#MoveDirectAbsolute : moveDirectAbsoluteExecute := FALSE;
                            AxisGroupCmd#MoveDirectRelative : moveDirectRelativeExecute := FALSE;
                            AxisGroupCmd#GroupHalt : groupHaltExecute := FALSE;
                        END_CASE;

                        hasPending := FALSE;
                    END_IF;

                    commandAborted := TRUE;
                    internalStatus := AxisGroupInternalStatus#Standby;
                ELSE
                    pendingCmd := cmd;
                    pendingEndPoint := endPoint;
                    pendingAuxPoint := auxPoint;
                    pendingVelocity := velocity;
                    hasPending := TRUE;
                    oldCmd := pendingCmd;

                    CASE pendingCmd OF
                        AxisGroupCmd#MoveLinearAbsolute : moveLinearAbsoluteExecute := TRUE;
                        AxisGroupCmd#MoveLinearRelative : moveLinearRelativeExecute := TRUE;
                        AxisGroupCmd#MoveCircularAbsolute : moveCircularAbsoluteExecute := TRUE;
                        AxisGroupCmd#MoveCircularRelative : moveCircularRelativeExecute := TRUE;
                        AxisGroupCmd#MoveDirectAbsolute : moveDirectAbsoluteExecute := TRUE;
                        AxisGroupCmd#MoveDirectRelative : moveDirectRelativeExecute := TRUE;
                        AxisGroupCmd#GroupHalt : groupHaltExecute := TRUE;
                    ELSE
                        hasPending := FALSE;
                        commandAborted := TRUE;
                        internalStatus := AxisGroupInternalStatus#Standby;
                    END_CASE;
                END_IF;
            END_IF;

        AxisGroupInternalStatus#CheckLinearRelativeState :
            IF cmd <> oldCmd THEN
                commandExecuted := FALSE;
                internalStatus := AxisGroupInternalStatus#Standby;
            END_IF;

        (* MoveCircularAbsolute *)
        AxisGroupInternalStatus#MoveCircularAbsoluteState :

            IF moveCircularAbsolute.Done THEN
                moveCircularAbsoluteExecute := FALSE;
                IF hasPending THEN
                    hasPending := FALSE;
                    oldCmd := pendingCmd;
                    oldEndPoint := pendingEndPoint;
                    oldAuxPoint := pendingAuxPoint;
                    oldVelocity := pendingVelocity;
                    commandExecuted := FALSE;
                    commandAborted := FALSE;

                    CASE oldCmd OF
                        AxisGroupCmd#MoveLinearAbsolute : moveLinearAbsoluteExecute := TRUE; internalStatus := AxisGroupInternalStatus#MoveLinearAbsoluteState;
                        AxisGroupCmd#MoveLinearRelative : moveLinearRelativeExecute := TRUE; internalStatus := AxisGroupInternalStatus#MoveLinearRelativeState;
                        AxisGroupCmd#MoveCircularAbsolute : moveCircularAbsoluteExecute := TRUE; internalStatus := AxisGroupInternalStatus#MoveCircularAbsoluteState;
                        AxisGroupCmd#MoveCircularRelative : moveCircularRelativeExecute := TRUE; internalStatus := AxisGroupInternalStatus#MoveCircularRelativeState;
                        AxisGroupCmd#MoveDirectAbsolute : moveDirectAbsoluteExecute := TRUE; internalStatus := AxisGroupInternalStatus#MoveDirectAbsoluteState;
                        AxisGroupCmd#MoveDirectRelative : moveDirectRelativeExecute := TRUE; internalStatus := AxisGroupInternalStatus#MoveDirectRelativeState;
                        AxisGroupCmd#GroupHalt : groupHaltExecute := TRUE; internalStatus := AxisGroupInternalStatus#HaltState;
                    ELSE
                        internalStatus := AxisGroupInternalStatus#Standby;
                    END_CASE;
                ELSE
                    commandExecuted := TRUE;
                    internalStatus := AxisGroupInternalStatus#CheckCircularAbsoluteState;
                END_IF;
            END_IF;

            IF cmd <> oldCmd THEN
                IF bufferMode = Motion.MC_BUFFER_MODE#aborting OR hasPending THEN
                    moveCircularAbsoluteExecute := FALSE;
                    IF hasPending THEN
                        CASE pendingCmd OF
                            AxisGroupCmd#MoveLinearAbsolute : moveLinearAbsoluteExecute := FALSE;
                            AxisGroupCmd#MoveLinearRelative : moveLinearRelativeExecute := FALSE;
                            AxisGroupCmd#MoveCircularAbsolute : moveCircularAbsoluteExecute := FALSE;
                            AxisGroupCmd#MoveCircularRelative : moveCircularRelativeExecute := FALSE;
                            AxisGroupCmd#MoveDirectAbsolute : moveDirectAbsoluteExecute := FALSE;
                            AxisGroupCmd#MoveDirectRelative : moveDirectRelativeExecute := FALSE;
                            AxisGroupCmd#GroupHalt : groupHaltExecute := FALSE;
                        END_CASE;

                        hasPending := FALSE;
                    END_IF;

                    commandAborted := TRUE;
                    internalStatus := AxisGroupInternalStatus#Standby;
                ELSE
                    pendingCmd := cmd;
                    pendingEndPoint := endPoint;
                    pendingAuxPoint := auxPoint;
                    pendingVelocity := velocity;
                    hasPending := TRUE;
                    oldCmd := pendingCmd;

                    CASE pendingCmd OF
                        AxisGroupCmd#MoveLinearAbsolute : moveLinearAbsoluteExecute := TRUE;
                        AxisGroupCmd#MoveLinearRelative : moveLinearRelativeExecute := TRUE;
                        AxisGroupCmd#MoveCircularAbsolute : moveCircularAbsoluteExecute := TRUE;
                        AxisGroupCmd#MoveCircularRelative : moveCircularRelativeExecute := TRUE;
                        AxisGroupCmd#MoveDirectAbsolute : moveDirectAbsoluteExecute := TRUE;
                        AxisGroupCmd#MoveDirectRelative : moveDirectRelativeExecute := TRUE;
                        AxisGroupCmd#GroupHalt : groupHaltExecute := TRUE;
                    ELSE
                        hasPending := FALSE;
                        commandAborted := TRUE;
                        internalStatus := AxisGroupInternalStatus#Standby;
                    END_CASE;
                END_IF;
            END_IF;

        AxisGroupInternalStatus#CheckCircularAbsoluteState :
            IF cmd <> oldCmd THEN
                commandExecuted := FALSE;
                internalStatus := AxisGroupInternalStatus#Standby;
            END_IF;

        (* MoveCircularRelative *)
        AxisGroupInternalStatus#MoveCircularRelativeState :

            IF moveCircularRelative.Done THEN
                moveCircularRelativeExecute := FALSE;
                IF hasPending THEN
                    hasPending := FALSE;
                    oldCmd := pendingCmd;
                    oldEndPoint := pendingEndPoint;
                    oldAuxPoint := pendingAuxPoint;
                    oldVelocity := pendingVelocity;
                    commandExecuted := FALSE;
                    commandAborted := FALSE;

                    CASE oldCmd OF
                        AxisGroupCmd#MoveLinearAbsolute : moveLinearAbsoluteExecute := TRUE; internalStatus := AxisGroupInternalStatus#MoveLinearAbsoluteState;
                        AxisGroupCmd#MoveLinearRelative : moveLinearRelativeExecute := TRUE; internalStatus := AxisGroupInternalStatus#MoveLinearRelativeState;
                        AxisGroupCmd#MoveCircularAbsolute : moveCircularAbsoluteExecute := TRUE; internalStatus := AxisGroupInternalStatus#MoveCircularAbsoluteState;
                        AxisGroupCmd#MoveCircularRelative : moveCircularRelativeExecute := TRUE; internalStatus := AxisGroupInternalStatus#MoveCircularRelativeState;
                        AxisGroupCmd#MoveDirectAbsolute : moveDirectAbsoluteExecute := TRUE; internalStatus := AxisGroupInternalStatus#MoveDirectAbsoluteState;
                        AxisGroupCmd#MoveDirectRelative : moveDirectRelativeExecute := TRUE; internalStatus := AxisGroupInternalStatus#MoveDirectRelativeState;
                        AxisGroupCmd#GroupHalt : groupHaltExecute := TRUE; internalStatus := AxisGroupInternalStatus#HaltState;
                    ELSE
                        internalStatus := AxisGroupInternalStatus#Standby;
                    END_CASE;
                ELSE
                    commandExecuted := TRUE;
                    internalStatus := AxisGroupInternalStatus#CheckCircularRelativeState;
                END_IF;
            END_IF;

            IF cmd <> oldCmd THEN
                IF bufferMode = Motion.MC_BUFFER_MODE#aborting OR hasPending THEN
                    moveCircularRelativeExecute := FALSE;
                    IF hasPending THEN
                        CASE pendingCmd OF
                            AxisGroupCmd#MoveLinearAbsolute : moveLinearAbsoluteExecute := FALSE;
                            AxisGroupCmd#MoveLinearRelative : moveLinearRelativeExecute := FALSE;
                            AxisGroupCmd#MoveCircularAbsolute : moveCircularAbsoluteExecute := FALSE;
                            AxisGroupCmd#MoveCircularRelative : moveCircularRelativeExecute := FALSE;
                            AxisGroupCmd#MoveDirectAbsolute : moveDirectAbsoluteExecute := FALSE;
                            AxisGroupCmd#MoveDirectRelative : moveDirectRelativeExecute := FALSE;
                            AxisGroupCmd#GroupHalt : groupHaltExecute := FALSE;
                        END_CASE;

                        hasPending := FALSE;
                    END_IF;

                    commandAborted := TRUE;
                    internalStatus := AxisGroupInternalStatus#Standby;
                ELSE
                    pendingCmd := cmd;
                    pendingEndPoint := endPoint;
                    pendingAuxPoint := auxPoint;
                    pendingVelocity := velocity;
                    hasPending := TRUE;
                    oldCmd := pendingCmd;

                    CASE pendingCmd OF
                        AxisGroupCmd#MoveLinearAbsolute : moveLinearAbsoluteExecute := TRUE;
                        AxisGroupCmd#MoveLinearRelative : moveLinearRelativeExecute := TRUE;
                        AxisGroupCmd#MoveCircularAbsolute : moveCircularAbsoluteExecute := TRUE;
                        AxisGroupCmd#MoveCircularRelative : moveCircularRelativeExecute := TRUE;
                        AxisGroupCmd#MoveDirectAbsolute : moveDirectAbsoluteExecute := TRUE;
                        AxisGroupCmd#MoveDirectRelative : moveDirectRelativeExecute := TRUE;
                        AxisGroupCmd#GroupHalt : groupHaltExecute := TRUE;
                    ELSE
                        hasPending := FALSE;
                        commandAborted := TRUE;
                        internalStatus := AxisGroupInternalStatus#Standby;
                    END_CASE;
                END_IF;
            END_IF;

        AxisGroupInternalStatus#CheckCircularRelativeState :
            IF cmd <> oldCmd THEN
                commandExecuted := FALSE;
                internalStatus := AxisGroupInternalStatus#Standby;
            END_IF;

        (* MoveDirectAbsolute - no velocity/acceleration/deceleration/jerk inputs *)
        AxisGroupInternalStatus#MoveDirectAbsoluteState :

            IF moveDirectAbsolute.Done THEN
                moveDirectAbsoluteExecute := FALSE;
                IF hasPending THEN
                    hasPending := FALSE;
                    oldCmd := pendingCmd;
                    oldEndPoint := pendingEndPoint;
                    oldAuxPoint := pendingAuxPoint;
                    oldVelocity := pendingVelocity;
                    commandExecuted := FALSE;
                    commandAborted := FALSE;
                    CASE oldCmd OF
                        AxisGroupCmd#MoveLinearAbsolute : moveLinearAbsoluteExecute := TRUE; internalStatus := AxisGroupInternalStatus#MoveLinearAbsoluteState;
                        AxisGroupCmd#MoveLinearRelative : moveLinearRelativeExecute := TRUE; internalStatus := AxisGroupInternalStatus#MoveLinearRelativeState;
                        AxisGroupCmd#MoveCircularAbsolute : moveCircularAbsoluteExecute := TRUE; internalStatus := AxisGroupInternalStatus#MoveCircularAbsoluteState;
                        AxisGroupCmd#MoveCircularRelative : moveCircularRelativeExecute := TRUE; internalStatus := AxisGroupInternalStatus#MoveCircularRelativeState;
                        AxisGroupCmd#MoveDirectAbsolute : moveDirectAbsoluteExecute := TRUE; internalStatus := AxisGroupInternalStatus#MoveDirectAbsoluteState;
                        AxisGroupCmd#MoveDirectRelative : moveDirectRelativeExecute := TRUE; internalStatus := AxisGroupInternalStatus#MoveDirectRelativeState;
                        AxisGroupCmd#GroupHalt : groupHaltExecute := TRUE; internalStatus := AxisGroupInternalStatus#HaltState;
                    ELSE
                        internalStatus := AxisGroupInternalStatus#Standby;
                    END_CASE;
                ELSE
                    commandExecuted := TRUE;
                    internalStatus := AxisGroupInternalStatus#CheckDirectAbsoluteState;
                END_IF;
            END_IF;

            IF cmd <> oldCmd THEN
                IF bufferMode = Motion.MC_BUFFER_MODE#aborting OR hasPending THEN
                    moveDirectAbsoluteExecute := FALSE;
                    IF hasPending THEN
                        CASE pendingCmd OF
                            AxisGroupCmd#MoveLinearAbsolute : moveLinearAbsoluteExecute := FALSE;
                            AxisGroupCmd#MoveLinearRelative : moveLinearRelativeExecute := FALSE;
                            AxisGroupCmd#MoveCircularAbsolute : moveCircularAbsoluteExecute := FALSE;
                            AxisGroupCmd#MoveCircularRelative : moveCircularRelativeExecute := FALSE;
                            AxisGroupCmd#MoveDirectAbsolute : moveDirectAbsoluteExecute := FALSE;
                            AxisGroupCmd#MoveDirectRelative : moveDirectRelativeExecute := FALSE;
                            AxisGroupCmd#GroupHalt : groupHaltExecute := FALSE;
                        END_CASE;
                        hasPending := FALSE;
                    END_IF;
                    commandAborted := TRUE;
                    internalStatus := AxisGroupInternalStatus#Standby;
                ELSE
                    pendingCmd := cmd;
                    pendingEndPoint := endPoint;
                    pendingAuxPoint := auxPoint;
                    pendingVelocity := velocity;
                    hasPending := TRUE;
                    oldCmd := pendingCmd;
                    CASE pendingCmd OF
                        AxisGroupCmd#MoveLinearAbsolute : moveLinearAbsoluteExecute := TRUE;
                        AxisGroupCmd#MoveLinearRelative : moveLinearRelativeExecute := TRUE;
                        AxisGroupCmd#MoveCircularAbsolute : moveCircularAbsoluteExecute := TRUE;
                        AxisGroupCmd#MoveCircularRelative : moveCircularRelativeExecute := TRUE;
                        AxisGroupCmd#MoveDirectAbsolute : moveDirectAbsoluteExecute := TRUE;
                        AxisGroupCmd#MoveDirectRelative : moveDirectRelativeExecute := TRUE;
                        AxisGroupCmd#GroupHalt : groupHaltExecute := TRUE;
                    ELSE
                        hasPending := FALSE;
                        commandAborted := TRUE;
                        internalStatus := AxisGroupInternalStatus#Standby;
                    END_CASE;
                END_IF;
            END_IF;

        AxisGroupInternalStatus#CheckDirectAbsoluteState :
            IF cmd <> oldCmd THEN
                commandExecuted := FALSE;
                internalStatus := AxisGroupInternalStatus#Standby;
            END_IF;

        (* MoveDirectRelative - no velocity/acceleration/deceleration/jerk inputs *)
        AxisGroupInternalStatus#MoveDirectRelativeState :

            IF moveDirectRelative.Done THEN
                moveDirectRelativeExecute := FALSE;
                IF hasPending THEN
                    hasPending := FALSE;
                    oldCmd := pendingCmd;
                    oldEndPoint := pendingEndPoint;
                    oldAuxPoint := pendingAuxPoint;
                    oldVelocity := pendingVelocity;
                    commandExecuted := FALSE;
                    commandAborted := FALSE;
                    CASE oldCmd OF
                        AxisGroupCmd#MoveLinearAbsolute : moveLinearAbsoluteExecute := TRUE; internalStatus := AxisGroupInternalStatus#MoveLinearAbsoluteState;
                        AxisGroupCmd#MoveLinearRelative : moveLinearRelativeExecute := TRUE; internalStatus := AxisGroupInternalStatus#MoveLinearRelativeState;
                        AxisGroupCmd#MoveCircularAbsolute : moveCircularAbsoluteExecute := TRUE; internalStatus := AxisGroupInternalStatus#MoveCircularAbsoluteState;
                        AxisGroupCmd#MoveCircularRelative : moveCircularRelativeExecute := TRUE; internalStatus := AxisGroupInternalStatus#MoveCircularRelativeState;
                        AxisGroupCmd#MoveDirectAbsolute : moveDirectAbsoluteExecute := TRUE; internalStatus := AxisGroupInternalStatus#MoveDirectAbsoluteState;
                        AxisGroupCmd#MoveDirectRelative : moveDirectRelativeExecute := TRUE; internalStatus := AxisGroupInternalStatus#MoveDirectRelativeState;
                        AxisGroupCmd#GroupHalt : groupHaltExecute := TRUE; internalStatus := AxisGroupInternalStatus#HaltState;
                    ELSE
                        internalStatus := AxisGroupInternalStatus#Standby;
                    END_CASE;
                ELSE
                    commandExecuted := TRUE;
                    internalStatus := AxisGroupInternalStatus#CheckDirectRelativeState;
                END_IF;
            END_IF;

            IF cmd <> oldCmd THEN
                IF bufferMode = Motion.MC_BUFFER_MODE#aborting OR hasPending THEN
                    moveDirectRelativeExecute := FALSE;
                    IF hasPending THEN
                        CASE pendingCmd OF
                            AxisGroupCmd#MoveLinearAbsolute : moveLinearAbsoluteExecute := FALSE;
                            AxisGroupCmd#MoveLinearRelative : moveLinearRelativeExecute := FALSE;
                            AxisGroupCmd#MoveCircularAbsolute : moveCircularAbsoluteExecute := FALSE;
                            AxisGroupCmd#MoveCircularRelative : moveCircularRelativeExecute := FALSE;
                            AxisGroupCmd#MoveDirectAbsolute : moveDirectAbsoluteExecute := FALSE;
                            AxisGroupCmd#MoveDirectRelative : moveDirectRelativeExecute := FALSE;
                            AxisGroupCmd#GroupHalt : groupHaltExecute := FALSE;
                        END_CASE;
                        hasPending := FALSE;
                    END_IF;
                    commandAborted := TRUE;
                    internalStatus := AxisGroupInternalStatus#Standby;
                ELSE
                    pendingCmd := cmd;
                    pendingEndPoint := endPoint;
                    pendingAuxPoint := auxPoint;
                    pendingVelocity := velocity;
                    hasPending := TRUE;
                    oldCmd := pendingCmd;
                    CASE pendingCmd OF
                        AxisGroupCmd#MoveLinearAbsolute : moveLinearAbsoluteExecute := TRUE;
                        AxisGroupCmd#MoveLinearRelative : moveLinearRelativeExecute := TRUE;
                        AxisGroupCmd#MoveCircularAbsolute : moveCircularAbsoluteExecute := TRUE;
                        AxisGroupCmd#MoveCircularRelative : moveCircularRelativeExecute := TRUE;
                        AxisGroupCmd#MoveDirectAbsolute : moveDirectAbsoluteExecute := TRUE;
                        AxisGroupCmd#MoveDirectRelative : moveDirectRelativeExecute := TRUE;
                        AxisGroupCmd#GroupHalt : groupHaltExecute  := TRUE;
                    ELSE
                        hasPending := FALSE;
                        commandAborted := TRUE;
                        internalStatus := AxisGroupInternalStatus#Standby;
                    END_CASE;
                END_IF;
            END_IF;

        AxisGroupInternalStatus#CheckDirectRelativeState :
            IF cmd <> oldCmd THEN
                commandExecuted := FALSE;
                internalStatus := AxisGroupInternalStatus#Standby;
            END_IF;

        (* GroupHalt - abortable; decelerates to standstill on path. *)
        AxisGroupInternalStatus#HaltState :
            IF haltGroup.Done THEN
                groupHaltExecute := FALSE;
                IF hasPending THEN
                    hasPending := FALSE;
                    oldCmd := pendingCmd;
                    oldEndPoint := pendingEndPoint;
                    oldAuxPoint := pendingAuxPoint;
                    oldVelocity := pendingVelocity;
                    commandExecuted := FALSE;
                    commandAborted := FALSE;
                    CASE oldCmd OF
                        AxisGroupCmd#MoveLinearAbsolute : moveLinearAbsoluteExecute := TRUE; internalStatus := AxisGroupInternalStatus#MoveLinearAbsoluteState;
                        AxisGroupCmd#MoveLinearRelative : moveLinearRelativeExecute := TRUE; internalStatus := AxisGroupInternalStatus#MoveLinearRelativeState;
                        AxisGroupCmd#MoveCircularAbsolute : moveCircularAbsoluteExecute := TRUE; internalStatus := AxisGroupInternalStatus#MoveCircularAbsoluteState;
                        AxisGroupCmd#MoveCircularRelative : moveCircularRelativeExecute := TRUE; internalStatus := AxisGroupInternalStatus#MoveCircularRelativeState;
                        AxisGroupCmd#MoveDirectAbsolute : moveDirectAbsoluteExecute := TRUE; internalStatus := AxisGroupInternalStatus#MoveDirectAbsoluteState;
                        AxisGroupCmd#MoveDirectRelative : moveDirectRelativeExecute := TRUE; internalStatus := AxisGroupInternalStatus#MoveDirectRelativeState;
                        AxisGroupCmd#GroupHalt : groupHaltExecute := TRUE; internalStatus := AxisGroupInternalStatus#HaltState;
                    ELSE
                        internalStatus := AxisGroupInternalStatus#Standby;
                    END_CASE;
                ELSE
                    commandExecuted := TRUE;
                    internalStatus := AxisGroupInternalStatus#Standby;
                END_IF;
            END_IF;

            (* MC_GroupHalt is abortable - a new motion command supersedes it *)
            IF cmd <> oldCmd THEN
                IF bufferMode = Motion.MC_BUFFER_MODE#aborting OR hasPending THEN
                    groupHaltExecute := FALSE;
                    IF hasPending THEN
                        CASE pendingCmd OF
                            AxisGroupCmd#MoveLinearAbsolute : moveLinearAbsoluteExecute := FALSE;
                            AxisGroupCmd#MoveLinearRelative : moveLinearRelativeExecute := FALSE;
                            AxisGroupCmd#MoveCircularAbsolute : moveCircularAbsoluteExecute := FALSE;
                            AxisGroupCmd#MoveCircularRelative : moveCircularRelativeExecute := FALSE;
                            AxisGroupCmd#MoveDirectAbsolute : moveDirectAbsoluteExecute := FALSE;
                            AxisGroupCmd#MoveDirectRelative : moveDirectRelativeExecute := FALSE;
                            AxisGroupCmd#GroupHalt : groupHaltExecute := FALSE;
                        END_CASE;
                        hasPending := FALSE;
                    END_IF;
                    commandAborted := TRUE;
                    internalStatus := AxisGroupInternalStatus#Standby;
                ELSE
                    pendingCmd := cmd;
                    pendingEndPoint := endPoint;
                    pendingAuxPoint := auxPoint;
                    pendingVelocity := velocity;
                    hasPending := TRUE;
                    oldCmd := pendingCmd;
                    CASE pendingCmd OF
                        AxisGroupCmd#MoveLinearAbsolute : moveLinearAbsoluteExecute := TRUE;
                        AxisGroupCmd#MoveLinearRelative : moveLinearRelativeExecute := TRUE;
                        AxisGroupCmd#MoveCircularAbsolute : moveCircularAbsoluteExecute := TRUE;
                        AxisGroupCmd#MoveCircularRelative : moveCircularRelativeExecute := TRUE;
                        AxisGroupCmd#MoveDirectAbsolute : moveDirectAbsoluteExecute := TRUE;
                        AxisGroupCmd#MoveDirectRelative : moveDirectRelativeExecute := TRUE;
                        AxisGroupCmd#GroupHalt : groupHaltExecute := TRUE;
                    ELSE
                        hasPending := FALSE;
                        commandAborted := TRUE;
                        internalStatus := AxisGroupInternalStatus#Standby;
                    END_CASE;
                END_IF;
            END_IF;

        (*
         * GroupStop - level-driven; Execute must stay TRUE until Done.
         * NOT abortable by any other motion command.
         *)
        AxisGroupInternalStatus#StoppingState :
            IF stopGroup.Done THEN
                groupStopExecute := FALSE;
                hasPending := FALSE; (* pending commands are discarded - stop is unconditional *)
                commandExecuted := TRUE;
                internalStatus := AxisGroupInternalStatus#Standby;
            END_IF;
            (* cmd changes are intentionally ignored here - MC_GroupStop is NOT abortable *)
    END_CASE;
END_IF; (* End error-recovery guard *)

(*
 * Status Handler - level-triggered, unconditional, every cycle.
 * Priority mirrors PLCopen group FSM: ErrorStop > Stopping > Moving > Standby > Disabled
 *)
IF readGroupStatus.GroupErrorStop THEN
    status := AxisGroupStatus#ErrorStop;
ELSIF readGroupStatus.GroupStopping THEN
    status := AxisGroupStatus#Stopping;
ELSIF readGroupStatus.GroupMoving THEN
    status := AxisGroupStatus#Moving;
ELSIF readGroupStatus.GroupStandby THEN
    status := AxisGroupStatus#Standby;
ELSE
    status := AxisGroupStatus#Disabled;
END_IF;

(*
 * PLCopen FB calls - unconditional every PLC cycle.
 * Execute / Enable signals are generated exclusively by the FSM above.
 * All motion parameters flow directly from VAR_INPUT each cycle.
 *)

(* Group management *)
enableGroup(
    AxisGroup := group,
    Execute := groupEnableExecute
);

resetGroup(
    AxisGroup := group,
    Execute := groupResetExecute
);

(* Diagnostics - always active *)
readGroupStatus(
    AxisGroup := group,
    Enable := TRUE
);

readGroupError(
    AxisGroup := group,
    Enable := TRUE
);
groupErrorId := readGroupError.GroupErrorID;

readGroupActPos(
    AxisGroup := group,
    Enable := TRUE,
    CoordSystem := CoordMotion.SMC_COORD_SYSTEM#MCS
);
actualPosition := readGroupActPos.Position;

readGroupActVel(
    AxisGroup := group,
    Enable := TRUE,
    CoordSystem := CoordMotion.SMC_COORD_SYSTEM#MCS
);
actualVelocity := readGroupActVel.Velocity;

(* Override - active when enabled *)
groupSetOverride(
    AxisGroup := group,
    Enable := overrideEnable,
    VelFactor := velFactor,
    AccFactor := accFactor,
    JerkFactor := jerkFactor
);

(* Motion - Execute signals set exclusively by FSM *)
moveLinearAbsolute(
    AxisGroup := group,
    Execute := moveLinearAbsoluteExecute,
    Position := endPoint,
    Velocity := velocity,
    Acceleration := acceleration,
    Deceleration := deceleration,
    Jerk := jerk,
    CoordSystem := coordinateSystem,
    BufferMode := bufferMode,
    TransitionMode := transitionMode,
    TransitionParameter := transParamArr
);

moveLinearRelative(
    AxisGroup := group,
    Execute := moveLinearRelativeExecute,
    Distance := endPoint,
    Velocity := velocity,
    Acceleration := acceleration,
    Deceleration := deceleration,
    Jerk := jerk,
    CoordSystem := coordinateSystem,
    BufferMode := bufferMode,
    TransitionMode := transitionMode,
    TransitionParameter := transParamArr
);

moveCircularAbsolute(
    AxisGroup := group,
    Execute := moveCircularAbsoluteExecute,
    CircMode := circMode,
    AuxPoint := auxPoint,
    EndPoint := endPoint,
    PathChoice := pathChoice,
    Velocity := velocity,
    Acceleration := acceleration,
    Deceleration := deceleration,
    Jerk := jerk,
    CoordSystem := coordinateSystem,
    BufferMode := bufferMode,
    TransitionMode := transitionMode,
    TransitionParameter := transParamArr
);

moveCircularRelative(
    AxisGroup := group,
    Execute := moveCircularRelativeExecute,
    CircMode := circMode,
    AuxPoint := auxPoint,
    EndPoint := endPoint,
    PathChoice := pathChoice,
    Velocity := velocity,
    Acceleration := acceleration,
    Deceleration := deceleration,
    Jerk := jerk,
    CoordSystem := coordinateSystem,
    BufferMode := bufferMode,
    TransitionMode := transitionMode,
    TransitionParameter := transParamArr
);

(* MoveDirectAbsolute / MoveDirectRelative: no Velocity / Acceleration / Deceleration / Jerk inputs *)
moveDirectAbsolute(
    AxisGroup := group,
    Execute := moveDirectAbsoluteExecute,
    Position := endPoint,
    CoordSystem := coordinateSystem,
    BufferMode := bufferMode,
    TransitionMode := transitionMode,
    TransitionParameter := transParamArr
);

moveDirectRelative(
    AxisGroup := group,
    Execute := moveDirectRelativeExecute,
    Distance := endPoint,
    CoordSystem := coordinateSystem,
    BufferMode := bufferMode,
    TransitionMode := transitionMode,
    TransitionParameter := transParamArr
);

(*
 * MC_GroupHalt: abortable deceleration to standstill; stays on path.
 * Note: BufferMode is NOT a parameter of MC_GroupHalt in CODESYS CoordMotion.
 *)
haltGroup(
    AxisGroup := group,
    Execute := groupHaltExecute,
    Deceleration := deceleration,
    Jerk := jerk,
    AccFactor := REAL#1.0,
    JerkFactor := REAL#1.0
);

(* MC_GroupStop: emergency stop; level-driven; stays on path; NOT abortable *)
stopGroup(
    AxisGroup := group,
    Execute := groupStopExecute,
    Deceleration := deceleration,
    Jerk := jerk
);
END_FUNCTION_BLOCK

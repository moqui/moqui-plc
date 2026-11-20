(*
 * A trajectory as a fixed-size array of waypoints with shared motion dynamics.
 *
 * Intended use:
 *   1. moqui-device-gateway populates this struct from the TrajectoryPointComponent view
 *      and writes it to the PLC via MQTT/OPC UA.
 *      For the ephemeral path, moqui-device.export#Trajectory publishes the following
 *      JSON payload to the configured MQTT topic (e.g. moqui/robot/arm1/trajectory):
 *        { "approximatedFunctionId": "100051", "waypointCount": 10,
 *          "axes": { "J1": [θ0,θ1,...,θ9], "J2": [...], ..., "J6": [...] } }
 *      Each axis array contains pointCount LREAL values in radians (sequenceNum order).
 *      Mapping into this struct: J1→points[i].pos.x, J2→pos.y, J3→pos.z,
 *                                J4→pos.a, J5→pos.b, J6→pos.c; pointCount := waypointCount.
 *      A JsonToParametersMapper variant for robot trajectories would parse the nested
 *      "axes" object and iterate each float array, since the standard scalar mapper
 *      does not handle arrays or nested objects.
 *   2. The PLC iterates points[0..pointCount-1] in sequenceNum order, feeding each
 *      TrajectoryPoint.pos to AxisGroup.endPoint and dispatching the appropriate
 *      motion command (MoveLinearAbsolute, MoveDirectAbsolute, etc.).
 *
 * Blending rules applied per transition:
 *   - TrajectoryPoint.isBreakPoint = TRUE -> aborting + TMNone (exact stop, always wins)
 *   - TrajectoryPoint.blendingMode > 0 -> overrides this.blendingMode for that point
 *   - Otherwise -> bufferMode + transitionMode + blendingMode
 *
 * Source entity: moqui.math.Trajectory (approximatedFunctionId = trajectoryId)
 * moqui blending enum: moqui.math.ParametricPath.compositionMethodEnumId (PpcmPlc* values)
 *)
TYPE Trajectory : STRUCT
    (* moqui.math.Trajectory.approximatedFunctionId *)
    trajectoryId : STRING;
    (* Number of valid waypoints; execute points[0..pointCount-1] in order *)
    pointCount : DINT;
    (* Coordinate system applied to all points (MCS for Cartesian, ACS for joint-space) *)
    coordSystem : CoordMotion.SMC_COORD_SYSTEM;
    (* Shared dynamics applied to all CP moves between waypoints *)
    velocity : LREAL; (* [u/s] *)
    acceleration : LREAL; (* [u/s²] *)
    deceleration : LREAL; (* [u/s²] *)
    jerk : LREAL; (* [u/s³] *)
    (*
     * Default PLCopen buffer mode for transitions between non-break points.
     * moqui: ParametricPath.compositionMethodEnumId = PpcmPlcAborting / PpcmPlcBlendingLow / ...
     *)
    bufferMode : Motion.MC_BUFFER_MODE;
    (*
     * Default PLCopen transition mode (geometric blend shape at the corner).
     * moqui: ParametricPath.compositionMethodEnumId = PpcmPlcTMNone / PpcmPlcTMCornerDist / ...
     *)
    transitionMode : CoordMotion.MC_TRANSITION_MODE;
    (*
     * Default blend parameter for TMCornerDistance [mm] or TMConstantVelocity [u/s].
     * moqui: ParametricPathPoint.tolerance (per-point) or trajectory-level default here.
     *)
    blendingMode : LREAL;
    (* Waypoints in execution order; valid range: [0..pointCount-1] *)
    (* Array bound = TRAJECTORY_POINT_LIST_MAX_SIZE - 1 = 63. AX SIMATIC does not allow
       non-literal array bounds in TYPE definitions; keep in sync with configuration.st. *)
    points : ARRAY[0..63] OF TrajectoryPoint;
END_STRUCT; END_TYPE

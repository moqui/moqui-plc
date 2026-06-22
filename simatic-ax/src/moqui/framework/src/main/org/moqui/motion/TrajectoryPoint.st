(*
 * One waypoint in a Trajectory.
 *
 * Position mapping to SMC_POS_REF.v[0..5]:
 *   Cartesian MCS  v[0]=X[mm]   v[1]=Y[mm]   v[2]=Z[mm]
 *                  v[3]=A[deg]  v[4]=B[deg]  v[5]=C[deg]
 *   Joint ACS      v[0]=J1[deg] v[1]=J2[deg] v[2]=J3[deg]
 *                  v[3]=J4[deg] v[4]=J5[deg] v[5]=J6[deg]
 *
 * Blending priority for the transition into this point (evaluated in order):
 *   1. isBreakPoint = TRUE -> exact stop: aborting + TMNone; all other fields ignored
 *   2. hasBlendingOverride = TRUE -> use this point's bufferMode + transitionMode + blendingMode
 *   3. Otherwise -> use Trajectory.bufferMode + transitionMode + blendingMode
 *
 * Gateway mapping from moqui:
 *   TrajectoryPoint.blendingEnumId (PpcmPlc* value) -> hasBlendingOverride = TRUE + bufferMode + transitionMode
 *   ParametricPathPoint.tolerance -> blendingMode (0.0 = use trajectory default)
 *)
TYPE TrajectoryPoint : STRUCT
    (* Execution order - moqui ApproximatedFunctionSample.sequenceNum *)
    sequenceNum : DINT;
    (* Time offset from trajectory start [ms] - moqui TrajectoryPoint.pointTimeOffsetMillis *)
    timeOffsetMs : UDINT;
    (* TRUE = exact stop; overrides all blending fields below *)
    isBreakPoint : BOOL;
    (*
     * TRUE = use this point's bufferMode + transitionMode instead of Trajectory defaults.
     * Set by the gateway when TrajectoryPoint.blendingEnumId is populated.
     *)
    hasBlendingOverride : BOOL;
    (*
     * Per-point blend parameter [mm for TMCornerDistance, u/s for TMConstantVelocity].
     * 0.0 = use Trajectory.blendingMode.
     * moqui: ParametricPathPoint.tolerance
     *)
    blendingMode : LREAL;
    (*
     * Per-point buffer mode override (active when hasBlendingOverride = TRUE).
     * moqui: TrajectoryPoint.blendingEnumId -> PpcmPlcAborting / PpcmPlcBlendingLow / ...
     *)
    bufferMode : Motion.MC_BUFFER_MODE;
    (*
     * Per-point transition mode override (active when hasBlendingOverride = TRUE).
     * moqui: TrajectoryPoint.blendingEnumId → PpcmPlcTMNone / PpcmPlcTMCornerDist / ...
     *)
    transitionMode: CoordMotion.MC_TRANSITION_MODE;
    (* 6-DOF position in the active coordinate system *)
    pos : CoordMotion.SMC_POS_REF;
END_STRUCT; END_TYPE

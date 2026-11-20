(* Signal actions.
 * The definition of each action role is a designer choice.
 * SignalMgmt combines the actions of the active signals with OR (cumulativeOutputAction):
 * every action must be a distinct bit.
 *)
TYPE SignalOutputAction : (
	None := 16#0000,
	EmergencyStop := 16#0001,
	ImmediateStop := 16#0002,
	OnPhaseStop := 16#0004,
    Inhibition := 16#0008
	(* etc. *)
) DWORD; END_TYPE

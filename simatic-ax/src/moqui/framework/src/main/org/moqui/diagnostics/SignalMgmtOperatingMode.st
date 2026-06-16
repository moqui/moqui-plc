TYPE SignalMgmtOperatingMode : (
    Reset, (* Complete reset *)
    Prepare, (* Pre-processing phase where the reset edges valid for the entire scan are prepared *)
    Process (* Evaluate and process the state of a single specific signal *)
); END_TYPE

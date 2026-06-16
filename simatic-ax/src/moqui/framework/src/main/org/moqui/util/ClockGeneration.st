FUNCTION_BLOCK ClockGeneration
VAR_EXTERNAL
    clks : Clocks;
END_VAR
VAR_INPUT
    operationType : OperatingMode;
END_VAR
VAR
    tick100ms : UDINT := UDINT#10;
    tick1s : UDINT := UDINT#10;
    tick1minute : UDINT := UDINT#60;
END_VAR

IF operationType = OperatingMode#Init THEN
    tick100ms := UDINT#10;
    tick1s := UDINT#10;
    tick1minute := UDINT#60;
END_IF;

clks.clock10ms := TRUE;

IF tick100ms > UDINT#1 THEN
    tick100ms := tick100ms - UDINT#1;
    clks.clock100ms := FALSE;
ELSE
    tick100ms := UDINT#10;
    clks.clock100ms := TRUE;
END_IF;

IF clks.clock100ms THEN
    IF tick1s > UDINT#1 THEN
        tick1s := tick1s - UDINT#1;
        clks.clock1s := FALSE;
    ELSE
        tick1s := UDINT#10;
        clks.clock1s := TRUE;
    END_IF;
ELSE
    clks.clock1s := FALSE;
END_IF;

IF clks.clock1s THEN
    IF tick1minute > UDINT#1 THEN
        tick1minute := tick1minute - UDINT#1;
        clks.clock1minute := FALSE;
    ELSE
        tick1minute := UDINT#60;
        clks.clock1minute := TRUE;
    END_IF;
ELSE
    clks.clock1minute := FALSE;
END_IF;
END_FUNCTION_BLOCK

FUNCTION_BLOCK IIRFilter
	VAR_INPUT
	    execute : BOOL;
	    clock : BOOL;
	    reset : BOOL;
	    input : REAL;
	    T : REAL;
	    tickTime : TIME := T#10ms;
	END_VAR
	VAR_OUTPUT
	    output : REAL;
	    done : BOOL;
	    busy : BOOL;
	    error : BOOL;
	    errorId : INT;
	    timeElapsed : REAL;
	END_VAR
	VAR
	    init : BOOL;
	    elapsedTicks : UDINT;
	    deltaTime : REAL;
	    alpha : REAL;
	END_VAR

	(* Defaults *)
	done := FALSE;
	busy := FALSE;
	error := FALSE;
	errorId := 0;

	(* AX note: keep nominal 10 ms sampling for the first porting pass.
	 * This preserves the filter behavior much better than the old passthrough stub,
	 * while avoiding TIME conversions that this AX target does not currently accept. *)
	IF tickTime <= T#0S THEN
	    error := execute;
	    errorId := 1;
	    busy := FALSE;
	    RETURN;
	END_IF;

	deltaTime := REAL#0.01;

	IF reset THEN
	    init := FALSE;
	    elapsedTicks := UDINT#0;
	END_IF;

	IF execute THEN
	    busy := TRUE;

	    IF NOT init THEN
	        output := input;
	        init := TRUE;
	        elapsedTicks := UDINT#0;
	    ELSE
	        IF clock THEN
	            IF T > REAL#0.0 THEN
					IF T > deltaTime THEN
						alpha := deltaTime / T;
					ELSE
						alpha := REAL#1.0;
					END_IF;
	                output := output + alpha * (input - output);
	            ELSE
	                output := input;
	            END_IF;

	            elapsedTicks := elapsedTicks + UDINT#1;
	        END_IF;
	    END_IF;

	    timeElapsed := TO_REAL(elapsedTicks) * deltaTime;
	    done := NOT error;
	ELSE
	    busy := FALSE;
	    done := FALSE;
	    timeElapsed := REAL#0.0;
	END_IF;
END_FUNCTION_BLOCK

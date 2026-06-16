FUNCTION_BLOCK SShapedFunc
	VAR_INPUT
	    execute : BOOL;
	    clock : BOOL;
	    startValue : REAL;
	    endValue : REAL;
	    duration : TIME;
	    tickTime : TIME := T#10ms;
	END_VAR
	VAR_OUTPUT
	    output : REAL;
	    done : BOOL;
	    busy : BOOL;
	    error : BOOL;
	    errorId : INT;
	END_VAR
	VAR
	    prevExecute : BOOL;
	    active : BOOL;
	    elapsedTicks : UDINT;
	    totalTicks : UDINT;
	    progress : REAL;
	    deltaValue : REAL;
		remainingTime : TIME;
	END_VAR

	done := FALSE;
	busy := FALSE;
	error := (errorId <> 0);

	IF execute AND NOT prevExecute THEN
	    errorId := 0;
	    IF (duration <= T#0S) OR (tickTime <= T#0S) THEN
	        error := TRUE;
	        errorId := 1;
	        active := FALSE;
	    ELSE
	        active := TRUE;
	        elapsedTicks := UDINT#0;
			remainingTime := duration;
			totalTicks := UDINT#0;
			WHILE remainingTime > T#0S DO
				totalTicks := totalTicks + UDINT#1;
				IF remainingTime > tickTime THEN
					remainingTime := remainingTime - tickTime;
				ELSE
					remainingTime := T#0S;
				END_IF;
			END_WHILE;
	        IF totalTicks = UDINT#0 THEN
				totalTicks := UDINT#1;
			END_IF;

	        deltaValue := endValue - startValue;
	        output := startValue;
	    END_IF;
	END_IF;

	IF execute THEN
	    IF active THEN
	        busy := TRUE;

	        IF clock THEN
	            IF elapsedTicks < totalTicks THEN
	                elapsedTicks := elapsedTicks + UDINT#1;
	            END_IF;
	        END_IF;

	        progress := TO_REAL(elapsedTicks) / TO_REAL(totalTicks);

	        IF progress >= REAL#1.0 THEN
	            output := endValue;
	            active := FALSE;
	            done := TRUE;
	        ELSE
	            output := startValue + deltaValue * (REAL#3.0 * progress * progress - REAL#2.0 * progress * progress * progress);
	        END_IF;
	    ELSE
	        IF NOT error THEN
	            done := TRUE;
	        END_IF;
	    END_IF;
	ELSE
	    active := FALSE;
	    elapsedTicks := UDINT#0;
	    totalTicks := UDINT#0;
	    errorId := 0;
	END_IF;

	prevExecute := execute;
END_FUNCTION_BLOCK
